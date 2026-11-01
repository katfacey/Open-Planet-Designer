# SPDX-License-Identifier: GPL-3.0-or-later
extends Node3D
const Location=preload("res://scripts/world/planet_location.gd")
const CellJob=preload("res://scripts/ecology/cell_job.gd")
const LayoutJob=preload("res://scripts/ecology/layout_job.gd")
const DiskCache=preload("res://scripts/streaming/disk_cache.gd")
var look: Resource=preload("res://earth_woodland.tres")
var definition: Resource
var provider: RefCounted
var origin := PackedFloat64Array([0.0,0.0,0.0])
var meshes: Dictionary={}
var triangles: Dictionary={}
var solid_prototypes: Dictionary={}
var cells: Dictionary={}
var wanted: Dictionary={}
var jobs: Dictionary={}
var current_nodes: Array=[]
var staged_nodes: Array=[]
var current_groups: Dictionary={}
var staged_groups: Dictionary={}
var layout_task: int=-1
var layout_job: RefCounted
var layout_queue: Array=[]
var cache_folder: String
var clock: float=0.0
var select_time: float=0.0
var layout_time: float=0.0
var catalogue_ready: bool=false
var enabled: bool=true
var placements: int=0
var expanded_triangles: int=0
var downgraded_instances: int=0
var budget_culled_instances: int=0
var cache_hits: int=0
var evictions: int=0
var upload_ms: float=0.0
var cache_time: float=0.0
var cache_bytes: int=0
var prune_task: int=-1
var prune_job: RefCounted
var camera_previous := PackedFloat64Array([0.0,0.0,0.0])

func configure(data: RefCounted,settings: Resource) -> void:
	provider=data; definition=settings
	cache_folder=ProjectSettings.globalize_path("user://ecology-cache/cells-2/"+(provider.signature+provider.identity_namespace+settings.cache_namespace).sha256_text())
	DirAccess.make_dir_recursive_absolute(cache_folder)
	await _load_catalogue()
	catalogue_ready=true

func _load_catalogue() -> void:
	if not FileAccess.file_exists("res://assets/catalog/catalog.json"): push_error("Native asset catalogue is missing"); return
	var catalogue: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/catalog/catalog.json"))
	var proxies: Dictionary={}
	if FileAccess.file_exists("res://assets/appearance/proxies.json"):
		proxies=JSON.parse_string(FileAccess.get_file_as_string("res://assets/appearance/proxies.json")).proxies
	for key in catalogue.prototypes:
		triangles[key]=int(catalogue.prototypes[key].triangles)
		var path: String="res://assets/catalog/"+catalogue.prototypes[key].file
		var proxy: Dictionary=proxies.get(catalogue.prototypes[key].kind,{}) if int(catalogue.prototypes[key].level)==2 else {}
		if not proxy.is_empty(): path=proxy.file; triangles[key]=int(proxy.triangles); solid_prototypes[key]=true
		ResourceLoader.load_threaded_request(path)
		while ResourceLoader.load_threaded_get_status(path)==ResourceLoader.THREAD_LOAD_IN_PROGRESS: await get_tree().process_frame
		var resource := ResourceLoader.load_threaded_get(path)
		var root: Node=null
		var source: MeshInstance3D=null
		var mesh: ArrayMesh=null
		if resource is ArrayMesh: mesh=resource.duplicate()
		elif resource is PackedScene:
			root=resource.instantiate(); source=_find_mesh(root)
			if source!=null: mesh=source.mesh.duplicate()
		if mesh!=null:
			for surface in mesh.get_surface_count():
				var material: Material=source.get_active_material(surface) if source!=null else mesh.surface_get_material(surface)
				mesh.surface_set_material(surface,look.prepare_material(material,catalogue.prototypes[key].kind))
			meshes[key]=mesh
		else: push_error("Cannot load native model "+path)
		if root!=null: root.free()
		await get_tree().process_frame
	# Distant crowns retain their original coverage; near proxies add real wood.
	for kind in proxies:
		var key: String=str(kind)+"_3"
		var packed: PackedScene=load("res://assets/catalog/"+catalogue.prototypes[str(kind)+"_2"].file)
		var instance := packed.instantiate(); var source := _find_mesh(instance)
		var mesh: ArrayMesh=source.mesh.duplicate()
		for surface in mesh.get_surface_count(): mesh.surface_set_material(surface,look.prepare_material(source.get_active_material(surface),kind))
		meshes[key]=mesh; triangles[key]=int(catalogue.prototypes[str(kind)+"_2"].triangles)
		instance.free()

func _find_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D: return node
	for child in node.get_children():
		var found := _find_mesh(child)
		if found!=null: return found
	return null

func tick(delta: float,camera: PackedFloat64Array) -> void:
	if not catalogue_ready: return
	clock+=delta; select_time-=delta; layout_time-=delta; cache_time-=delta
	if select_time<=0.0:
		_select_cells(camera); select_time=0.6
	for key in jobs.keys():
		var record: Dictionary=jobs[key]
		if not WorkerThreadPool.is_task_completed(record.id): continue
		WorkerThreadPool.wait_for_task_completion(record.id); jobs.erase(key)
		if wanted.has(key): cells[key]=record.job.result; cache_hits+=int(record.job.cache_hit)
	for key in cells.keys():
		if not wanted.has(key): cells.erase(key); evictions+=1
	var requests: Array=wanted.values()
	requests.sort_custom(func(a: Dictionary,b: Dictionary): return a.distance<b.distance)
	for tile in requests:
		if jobs.size()>=2: break
		if cells.has(tile.key) or jobs.has(tile.key): continue
		var job := CellJob.new(); job.provider=provider; job.tile=tile; job.ground=tile.ground
		job.cache_path=cache_folder+"/"+str(tile.key).replace("/","_")+".opdc"
		jobs[tile.key]={"job":job,"id":WorkerThreadPool.add_task(job.run,false,"Planet ecosystem "+str(tile.key))}
	if layout_task>=0 and WorkerThreadPool.is_task_completed(layout_task):
		WorkerThreadPool.wait_for_task_completion(layout_task); layout_task=-1
		layout_queue=layout_job.groups.values(); placements=layout_job.instance_count
		expanded_triangles=layout_job.expanded_triangles; downgraded_instances=layout_job.downgraded; budget_culled_instances=layout_job.budget_culled
		if layout_queue.is_empty():
			for node in current_nodes: node.queue_free()
			current_nodes.clear(); current_groups.clear()
	if layout_time<=0.0 and layout_task<0 and layout_queue.is_empty() and staged_nodes.is_empty():
		layout_job=LayoutJob.new(); layout_job.cells=cells.values(); layout_job.camera=camera.duplicate()
		layout_job.tree_reach=definition.tree_reach_m if enabled else 0.0; layout_job.ground_reach=definition.ground_reach_m if enabled else 0.0
		layout_job.tree_full=definition.tree_full_detail_m; layout_job.tree_medium=definition.tree_medium_detail_m
		layout_job.tree_impostor=definition.tree_impostor_start_m
		layout_job.cover_full=definition.cover_full_detail_m; layout_job.cover_medium=definition.cover_medium_detail_m
		layout_job.triangle_budget=definition.scatter_triangle_budget; layout_job.instance_budget=definition.instance_budget; layout_job.triangles=triangles.duplicate()
		layout_task=WorkerThreadPool.add_task(layout_job.run,false,"Planet vegetation LOD layout"); layout_time=0.5
	var started := Time.get_ticks_usec(); var deadline := started+int(definition.upload_budget_ms*1000.0)
	while not layout_queue.is_empty() and Time.get_ticks_usec()<deadline:
		var group: Dictionary=layout_queue.pop_back()
		if not meshes.has(group.prototype): continue
		var node: MultiMeshInstance3D=current_groups.get(group.key)
		var multi: MultiMesh
		if node==null or node.multimesh.buffer!=group.buffer:
			multi=MultiMesh.new(); multi.transform_format=MultiMesh.TRANSFORM_3D; multi.mesh=meshes[group.prototype]
			multi.instance_count=group.count; multi.buffer=group.buffer
		if node==null:
			node=MultiMeshInstance3D.new(); node.name=str(group.prototype); node.visible=false
			node.position=Location.local(group.centre,origin); node.set_meta("centre64",group.centre)
			if group.lod>=2 and not solid_prototypes.has(group.prototype): node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(node)
		staged_nodes.append(node); staged_groups[group.key]={"node":node,"multi":multi}
	if layout_queue.is_empty() and not staged_nodes.is_empty():
		for key in current_groups:
			if not staged_groups.has(key): current_groups[key].visible=false; current_groups[key].queue_free()
		current_groups.clear()
		for key in staged_groups:
			var entry: Dictionary=staged_groups[key]
			if entry.multi!=null: entry.node.multimesh=entry.multi
			current_groups[key]=entry.node
		current_nodes=staged_nodes; staged_nodes=[]
		staged_groups.clear()
		for node in current_nodes: node.visible=enabled
	# An empty layout must also retire an old population (e.g. ascent/toggle).
	if layout_task<0 and layout_job!=null and layout_job.groups.is_empty() and staged_nodes.is_empty():
		for node in current_nodes: node.queue_free()
		current_nodes.clear(); current_groups.clear()
	upload_ms=(Time.get_ticks_usec()-started)/1000.0
	if prune_task>=0 and WorkerThreadPool.is_task_completed(prune_task):
		WorkerThreadPool.wait_for_task_completion(prune_task); prune_task=-1; cache_bytes=prune_job.result_bytes
	if cache_time<=0.0 and prune_task<0:
		prune_job=DiskCache.new(); prune_job.root_folder=cache_folder.get_base_dir().get_base_dir(); prune_job.limit=definition.disk_cache_mb*524288
		prune_task=WorkerThreadPool.add_task(prune_job.run,false,"Ecology cache eviction"); cache_time=5.0

func _select_cells(camera: PackedFloat64Array) -> void:
	wanted.clear()
	if not enabled: return
	var d := Location.normalized(camera)
	if Location.radius(camera)-provider.radius_m-provider.height(d)>definition.tree_reach_m+150.0: return
	# Keep cell/plant spacing approximately physical as the planet radius changes.
	var address := Location.address(d)
	var level := clampi(int(round(log(provider.radius_m*2.0/96.0)/log(2.0))),0,24)
	var size := 1<<level
	var cx := int(floor((float(address.u)+1.0)*0.5*size)); var cy := int(floor((float(address.v)+1.0)*0.5*size))
	var width: float=provider.radius_m*2.0/size
	var reach: float=definition.tree_reach_m
	var count := mini(24,int(ceil(reach/(width*0.5)))+2)
	var candidates := []
	for y in range(-count,count+1):
		for x in range(-count,count+1):
			var raw := Location.tile_direction(Location.tile(address.face,level,cx+x,cy+y),0.5,0.5)
			var canonical := Location.address(raw)
			var tx := clampi(int(floor((float(canonical.u)+1.0)*0.5*size)),0,size-1)
			var ty := clampi(int(floor((float(canonical.v)+1.0)*0.5*size)),0,size-1)
			var tile := Location.tile(canonical.face,level,tx,ty)
			var centre := Location.point(Location.tile_direction(tile,0.5,0.5),provider.radius_m)
			var surface_camera := Location.point(d,provider.radius_m)
			var distance := Location.distance(surface_camera,centre)
			if distance>reach+width: continue
			tile.key+="/trees"; tile.ground=false; tile.distance=distance; candidates.append(tile)
	candidates.sort_custom(func(a: Dictionary,b: Dictionary): return a.distance<b.distance)
	for tile in candidates:
		if wanted.size()>=144: break
		wanted[tile.key]=tile
		if tile.distance<definition.ground_reach_m+width and wanted.size()<144:
			var ground: Dictionary=tile.duplicate(); ground.key=str(ground.key).replace("/trees","/ground"); ground.ground=true; wanted[ground.key]=ground

func set_origin(next: PackedFloat64Array) -> void:
	origin=next
	for node in current_nodes+staged_nodes: node.position=Location.local(node.get_meta("centre64"),origin)

func statistics() -> Dictionary:
	return {"ecology_cells":cells.size(),"ecology_pending":jobs.size(),"vegetation_instances":placements,"vegetation_batches":current_nodes.size(),"expanded_scatter_triangles":expanded_triangles,"downgraded_instances":downgraded_instances,"budget_culled_instances":budget_culled_instances,"ecology_cache_hits":cache_hits,"ecology_evictions":evictions,"ecology_upload_ms":upload_ms,"ecology_cache_bytes":cache_bytes,"asset_meshes":meshes.size()}

func shutdown() -> void:
	if prune_task>=0: WorkerThreadPool.wait_for_task_completion(prune_task); prune_task=-1
	if layout_task>=0: WorkerThreadPool.wait_for_task_completion(layout_task); layout_task=-1
	for job in jobs.values(): WorkerThreadPool.wait_for_task_completion(job.id)
	jobs.clear()

func _exit_tree() -> void:
	shutdown()
