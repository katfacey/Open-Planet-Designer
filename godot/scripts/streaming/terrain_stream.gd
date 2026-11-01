# SPDX-License-Identifier: GPL-3.0-or-later
extends Node3D
const Location=preload("res://scripts/world/planet_location.gd")
const TileMesh=preload("res://scripts/terrain/tile_mesh.gd")
const Selector=preload("res://scripts/terrain/tile_selector.gd")
const Job=preload("res://scripts/streaming/tile_job.gd")
const DiskCache=preload("res://scripts/streaming/disk_cache.gd")
const CoverageJob=preload("res://scripts/streaming/coverage_job.gd")
var provider: RefCounted
var job_type: Script=Job
var definition: Resource
var material: ShaderMaterial
var origin := PackedFloat64Array([0.0,0.0,0.0])
var selector := Selector.new()
var desired: Dictionary={}
var required: Dictionary={}
var resident: Dictionary={}
var active: Dictionary={}
var jobs: Dictionary={}
var pending_cover: Dictionary={}
var pending_meshes: Dictionary={}
var pending_masks: Dictionary={}
var cover_dirty: bool=true
var selection_task: int=-1
var selection_job: RefCounted
var coverage_task: int=-1
var coverage_job: RefCounted
var planning_cover: Dictionary={}
var demand_generation: int=0
var cache_folder: String
var clock: float=0.0
var reselect_time: float=0.0
var cache_time: float=0.0
var frame_upload_ms: float=0.0
var selection_ms: float=0.0
var completed: int=0
var discarded: int=0
var cache_hits: int=0
var corrupt_entries: int=0
var evictions: int=0
var peak_resident: int=0
var cache_bytes: int=0
var prune_task: int=-1
var prune_job: RefCounted
var worker_times: Array[float]=[]

func configure(data: RefCounted,settings: Resource,ground: ShaderMaterial,cache_directory: String="") -> void:
	provider=data; definition=settings; material=ground
	var root_folder := "user://terrain-cache" if cache_directory.is_empty() else cache_directory
	cache_folder=ProjectSettings.globalize_path(root_folder+"/patch-1/"+(provider.signature+settings.cache_namespace).sha256_text())
	DirAccess.make_dir_recursive_absolute(cache_folder)
	_prune_cache()

func tick(delta: float,camera: PackedFloat64Array,focal: float) -> void:
	clock+=delta; reselect_time-=delta; cache_time-=delta
	if selection_task>=0 and WorkerThreadPool.is_task_completed(selection_task):
		WorkerThreadPool.wait_for_task_completion(selection_task); selection_task=-1
		selector=selection_job; selection_ms=selection_job.elapsed_ms
		var next: Dictionary=selection_job.result
		if not _same_keys(next,desired):
			demand_generation+=1
			desired=next; required.clear(); pending_cover.clear(); pending_meshes.clear(); pending_masks.clear(); cover_dirty=true
			for tile in desired.values():
				var ancestor: Dictionary=tile.duplicate()
				while true:
					required[ancestor.key]=ancestor.duplicate()
					if ancestor.level==0: break
					ancestor=Location.tile(ancestor.face,ancestor.level-1,ancestor.x>>1,ancestor.y>>1)
	if reselect_time<=0.0 and selection_task<0:
		selection_job=Selector.new()
		selection_task=WorkerThreadPool.add_task(selection_job.run.bind(provider,definition.duplicate(),camera.duplicate(),focal),false,"Planet tile selection")
		reselect_time=0.35
	var deadline := Time.get_ticks_usec()+int(definition.upload_budget_ms*1000.0)
	var start := Time.get_ticks_usec()
	for key in jobs.keys():
		var record: Dictionary=jobs[key]
		if not WorkerThreadPool.is_task_completed(record.id): continue
		if Time.get_ticks_usec()>deadline: break
		WorkerThreadPool.wait_for_task_completion(record.id)
		var job: RefCounted=record.job
		jobs.erase(key); completed+=1; cache_hits+=int(job.cache_hit); corrupt_entries+=int(job.corrupt_cache)
		if worker_times.size()<10000: worker_times.append(job.worker_ms)
		if not required.has(key): discarded+=1; continue
		if resident.size()>=definition.resident_tile_limit: _evict_unneeded()
		if resident.size()>=definition.resident_tile_limit: discarded+=1; continue
		var instance := MeshInstance3D.new(); instance.name="Terrain_"+key.replace("/","_")
		instance.material_override=material; instance.visible=false
		instance.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if int(job.tile.level)>=12 else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(instance)
		resident[key]={"data":job.result,"node":instance,"mask":-1,"used":clock,"born":clock}
		instance.position=Location.local(job.result.centre,origin)
		cover_dirty=true
	peak_resident=maxi(peak_resident,resident.size())
	if coverage_task>=0 and WorkerThreadPool.is_task_completed(coverage_task):
		WorkerThreadPool.wait_for_task_completion(coverage_task); coverage_task=-1
		if coverage_job.generation==demand_generation and coverage_job.valid:
			pending_cover=coverage_job.cover; pending_masks=coverage_job.masks
		elif coverage_job.generation!=demand_generation: cover_dirty=true
		planning_cover.clear()
	if pending_cover.is_empty() and coverage_task<0 and cover_dirty:
		cover_dirty=false
		var proposed := {}
		for face in 6: _cover(Location.tile(face,0,0,0),proposed)
		if not _same_keys(proposed,active):
			planning_cover=proposed
			coverage_job=CoverageJob.new(); coverage_job.cover=proposed.duplicate(true); coverage_job.generation=demand_generation
			coverage_task=WorkerThreadPool.add_task(coverage_job.run,false,"Terrain seam planning")
	if not pending_cover.is_empty():
		for key in pending_cover:
			if Time.get_ticks_usec()>deadline: break
			var mask: int=pending_masks[key]
			var entry: Dictionary=resident[key]
			if entry.mask==mask or pending_meshes.has(key): continue
			var mesh := ArrayMesh.new()
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,TileMesh.arrays(entry.data,mask),[],{},Mesh.ARRAY_CUSTOM_RGBA_FLOAT<<Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT)
			pending_meshes[key]={"mesh":mesh,"mask":mask}
		var ready := true
		for key in pending_cover:
			if resident[key].mask!=pending_masks[key] and not pending_meshes.has(key): ready=false
		if ready:
			for key in active:
				if resident.has(key): resident[key].node.visible=false
			for key in pending_cover:
				var entry: Dictionary=resident[key]
				if pending_meshes.has(key):
					entry.node.mesh=pending_meshes[key].mesh; entry.mask=pending_meshes[key].mask
				entry.node.visible=true; entry.used=clock
			active=pending_cover.duplicate(); pending_cover.clear(); pending_meshes.clear(); pending_masks.clear()
	for key in active:
		var entry: Dictionary=resident[key]
		entry.node.set_instance_shader_parameter("terrain_morph",maxf(0.0,1.0-(clock-float(entry.born))/0.4))
	frame_upload_ms=(Time.get_ticks_usec()-start)/1000.0
	_evict_unneeded()
	# Only a bounded number of jobs exist: no unbounded worker/result backlog.
	var requests := []
	for tile in required.values():
		if resident.has(tile.key) or jobs.has(tile.key): continue
		var centre := Location.point(Location.tile_direction(tile,0.5,0.5),provider.radius_m)
		requests.append({"tile":tile,"score":float(tile.level)*100000000.0+Location.distance(camera,centre)})
	requests.sort_custom(func(a: Dictionary,b: Dictionary): return a.score<b.score)
	for request in requests:
		if jobs.size()>=definition.worker_limit or resident.size()+jobs.size()>=definition.resident_tile_limit: break
		var tile: Dictionary=request.tile
		var job: RefCounted=job_type.new(); job.provider=provider; job.tile=tile
		job.cache_path=cache_folder+"/"+str(tile.key).replace("/","_")+".opdc"
		var id := WorkerThreadPool.add_task(job.run,false,"Planet terrain "+str(tile.key))
		jobs[tile.key]={"job":job,"id":id}
	if prune_task>=0 and WorkerThreadPool.is_task_completed(prune_task):
		WorkerThreadPool.wait_for_task_completion(prune_task); prune_task=-1; cache_bytes=prune_job.result_bytes
	if cache_time<=0.0 and prune_task<0:
		prune_job=DiskCache.new(); prune_job.root_folder=cache_folder.get_base_dir().get_base_dir(); prune_job.limit=definition.disk_cache_mb*1048576
		prune_task=WorkerThreadPool.add_task(prune_job.run,false,"Terrain cache eviction"); cache_time=5.0

func _cover(tile: Dictionary,result: Dictionary) -> void:
	if not resident.has(tile.key): return
	if not desired.has(tile.key) and required.has(tile.key):
		var children := Location.children(tile)
		var complete := true
		for child in children:
			if not resident.has(child.key): complete=false
		if complete:
			for child in children: _cover(child,result)
			return
	result[tile.key]=tile

func _same_keys(a: Dictionary,b: Dictionary) -> bool:
	if a.size()!=b.size(): return false
	for key in a:
		if not b.has(key): return false
	return true

func _evict_unneeded() -> void:
	for key in resident.keys():
		if required.has(key) or active.has(key) or pending_cover.has(key) or planning_cover.has(key): continue
		resident[key].node.queue_free(); resident.erase(key); evictions+=1

func set_origin(next: PackedFloat64Array) -> void:
	origin=next
	for entry in resident.values(): entry.node.position=Location.local(entry.data.centre,origin)

func force_selection() -> void:
	reselect_time=0.0

func _prune_cache() -> void:
	cache_bytes=DiskCache.prune(cache_folder.get_base_dir().get_base_dir(),definition.disk_cache_mb*1048576)

func statistics() -> Dictionary:
	return {"resident_tiles":resident.size(),"active_tiles":active.size(),"requested_tiles":required.size(),"desired_leaves":desired.size(),
		"pending_workers":jobs.size(),"peak_resident_tiles":peak_resident,"completed_jobs":completed,"discarded_jobs":discarded,
		"cache_hits":cache_hits,"corrupt_cache_regenerated":corrupt_entries,"evictions":evictions,"disk_cache_bytes":cache_bytes,
		"upload_and_retire_ms":frame_upload_ms,"selection_worker_ms":selection_ms,"unmet_error_pixels":selector.unmet_error_pixels}

func shutdown() -> void:
	if coverage_task>=0: WorkerThreadPool.wait_for_task_completion(coverage_task); coverage_task=-1
	if prune_task>=0: WorkerThreadPool.wait_for_task_completion(prune_task); prune_task=-1
	if selection_task>=0: WorkerThreadPool.wait_for_task_completion(selection_task); selection_task=-1
	for record in jobs.values(): WorkerThreadPool.wait_for_task_completion(record.id)
	jobs.clear()

func _exit_tree() -> void:
	shutdown()
