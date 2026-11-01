# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
const Location=preload("res://scripts/world/planet_location.gd")
const Definition=preload("res://scripts/world/planet_definition.gd")
const Provider=preload("res://scripts/terrain/height_provider.gd")
const FieldNoise=preload("res://scripts/terrain/canonical_noise.gd")
const TileMesh=preload("res://scripts/terrain/tile_mesh.gd")
const Selector=preload("res://scripts/terrain/tile_selector.gd")
const Job=preload("res://scripts/streaming/tile_job.gd")
const CellJob=preload("res://scripts/ecology/cell_job.gd")
const Collision=preload("res://scripts/navigation/collision_bubble.gd")
const Layout=preload("res://scripts/ecology/layout_job.gd")
const DiskCache=preload("res://scripts/streaming/disk_cache.gd")
const CoverageJob=preload("res://scripts/streaming/coverage_job.gd")
var checks: Dictionary={}
var failed: bool=false

func _initialize() -> void:
	_run.call_deferred()

func check(name: String,passed: bool) -> void:
	checks[name]=passed
	if not passed: failed=true; push_error("FAILED: "+name)

func _run() -> void:
	var settings := Definition.new(); var provider := Provider.new(); provider.configure(settings)
	var fixture: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/native_scalar.json"))
	var matching := true
	for item in fixture.noise:
		var n := FieldNoise.sample(item.point[0],item.point[1],item.point[2],int(item.seed))
		for i in 4: matching=matching and absf(n[i]-float(item.sample[i]))<1e-12
	for item in fixture.directions:
		matching=matching and Location.distance(Location.direction(item.face,item.u,item.v),PackedFloat64Array(item.direction))<1e-14
	for item in fixture.heights:
		matching=matching and absf(provider.height(PackedFloat64Array(item.direction))-float(item.height_m))<1e-7
	check("cross_language_noise_height_and_legacy_cube_fixtures",matching)
	var roundtrip := true; var boundaries := true
	for face in 6:
		for u in [-1.0,-0.315,0.0,0.71,1.0]:
			for v in [-1.0,-0.24,0.0,0.63,1.0]:
				var d := Location.direction(face,u,v); var address := Location.address(d)
				var other := Location.direction(address.face,address.u,address.v)
				roundtrip=roundtrip and Location.distance(d,other)<1e-14
				if absf(u)==1.0 or absf(v)==1.0: boundaries=boundaries and absf(provider.height(d)-provider.height(other))<1e-7
	check("cube_faces_poles_corners_roundtrip",roundtrip)
	check("canonical_height_continuous_at_face_seams",boundaries)
	var point := PackedFloat64Array([6371000.0,0.0,0.0]); var origin := point.duplicate(); point[0]+=0.01
	check("centimetre_survives_planet_radius_before_local_float_conversion",absf(Location.local(point,origin).x-0.01)<1e-7)
	var trunk := {"centre":PackedFloat64Array([6371000.0,0.0,0.0]),"ground":false,"records":PackedFloat64Array([6371000.0,0,0,0,0,10,10,0,0,0,10,0,0,10,0.5,1])}
	var stopped := Collision.sweep(PackedFloat64Array([6371002.0,-3,0]),PackedFloat64Array([6371002.0,3,0]),[trunk])
	check("camera_sweep_stops_at_canonical_trunk",stopped[1]<-0.4 and stopped[1]>-0.5)
	var catalogue: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/catalog/catalog.json"))
	var layout := Layout.new(); layout.camera=PackedFloat64Array([6371002.0,1,0]); layout.tree_reach=350; layout.ground_reach=45
	var cell := {"records":trunk.records,"ids":PackedStringArray(["unit/tree"]),"centre":trunk.centre,"ground":false,"tile":{"key":"unit"}}
	layout.cells=[cell]
	for key in catalogue.prototypes: layout.triangles[key]=catalogue.prototypes[key].triangles
	layout.run()
	check("newly_visited_tree_can_select_source_hero_lod",layout.groups.has("unit/0/0"))
	layout.triangle_budget=8000; layout.run()
	check("scatter_budget_downgrades_without_reseeding_or_removing_tree",layout.instance_count==1 and layout.expanded_triangles<=8000 and layout.downgraded==1)
	layout.instance_budget=0; layout.run()
	check("instance_budget_is_hard_bound",layout.instance_count==0 and layout.budget_culled==1)
	var derivatives := true
	for p in [Vector3(-3.125,0.17,8.32),Vector3(191.3,-47.2,0.5)]:
		var n := FieldNoise.sample(p.x,p.y,p.z,42)
		var dx: float=(FieldNoise.sample(p.x+0.00001,p.y,p.z,42)[0]-FieldNoise.sample(p.x-0.00001,p.y,p.z,42)[0])/0.00002
		derivatives=derivatives and absf(dx-n[1])<0.00001
	check("noise_derivative_matches_numeric_reference",derivatives)
	var topology := true
	for mask in 16:
		var indices := TileMesh.indices(mask); var area := 0.0
		for i in range(0,indices.size(),3):
			var a := Vector2(indices[i]%33,indices[i]/33); var b := Vector2(indices[i+1]%33,indices[i+1]/33); var c := Vector2(indices[i+2]%33,indices[i+2]/33)
			area+=absf((b-a).cross(c-a))*0.5
			for index in [indices[i],indices[i+1],indices[i+2]]:
				topology=topology and index>=0 and index<TileMesh.VERTICES
				if mask&1 and index%33==0: topology=topology and (index/33)%2==0
				if mask&2 and index%33==32: topology=topology and (index/33)%2==0
				if mask&4 and index/33==0: topology=topology and index%2==0
				if mask&8 and index/33==32: topology=topology and (index%33)%2==0
		topology=topology and absf(area-1024.0)<0.001
	check("all_16_stitch_patterns_cover_patch_without_holes",topology)
	var selector := Selector.new(); var balanced := true; var bounded := true; var coverage := true
	settings.leaf_budget=96
	for address in [[2,0.08,0.11],[2,0.99999,0.03],[2,0.0,0.0],[0,0.99999,0.99999]]:
		var d := Location.direction(address[0],address[1],address[2])
		var camera := Location.point(d,settings.radius_m+provider.height(d)+2.0)
		var selection := selector.select(provider,settings,camera,600.0)
		bounded=bounded and selection.size()<=settings.leaf_budget
		var areas := PackedFloat64Array([0,0,0,0,0,0])
		for tile in selection.values():
			areas[tile.face]+=pow(0.25,float(tile.level))
			for edge in 4:
				var neighbour := Selector.neighbour(tile,edge,selection)
				balanced=balanced and not neighbour.is_empty() and abs(int(tile.level)-int(neighbour.get("level",0)))<=1
		for area in areas: coverage=coverage and absf(area-1.0)<1e-10
	check("selection_hard_leaf_budget_includes_balancing",bounded)
	check("selection_2_to_1_across_faces_and_poles",balanced)
	check("selection_covers_all_six_faces_exactly",coverage)
	var cover_job := CoverageJob.new(); cover_job.cover=selector.leaves.duplicate(true); cover_job.run()
	var handoff_guard := cover_job.valid
	cover_job.cover.clear()
	for face in 6:
		var coarse := Location.tile(face,0,0,0); cover_job.cover[coarse.key]=coarse
	cover_job.cover.erase(Location.tile_key(0,0,0,0))
	for child in Location.children(Location.tile(0,0,0,0)): cover_job.cover[child.key]=child
	cover_job.cover.erase(Location.tile_key(0,1,0,0))
	for child in Location.children(Location.tile(0,1,0,0)): cover_job.cover[child.key]=child
	cover_job.run(); handoff_guard=handoff_guard and not cover_job.valid
	cover_job.cover.erase(Location.tile_key(1,0,0,0)); cover_job.run()
	check("coverage_handoff_rejects_incomplete_or_unstitchable_partial_loading",handoff_guard and not cover_job.valid)
	var contact_settings := Definition.new()
	var contact_dir := Location.direction(2,0.0798,0.11015)
	var contact_camera := Location.point(contact_dir,provider.radius_m+provider.height(contact_dir)+2.2)
	var contact_selection := selector.select(provider,contact_settings,contact_camera,850.0)
	var centre_address := Location.address(contact_dir); var contact_spacing := INF
	for tile in contact_selection.values():
		if tile.face!=centre_address.face: continue
		var size := 1<<int(tile.level)
		if tile.x==int(floor((float(centre_address.u)+1.0)*0.5*size)) and tile.y==int(floor((float(centre_address.v)+1.0)*0.5*size)):
			contact_spacing=provider.radius_m*2.0/size/32.0
	check("foreground_contact_resolution_has_priority",contact_spacing<=0.45)
	var tile := Location.tile(2,18,141557,145489)
	var data := TileMesh.generate(provider,tile)
	check("mesh_uses_real_displaced_geometry",float(data.max_height)-float(data.min_height)>0.01)
	var same := TileMesh.generate(provider,tile)
	check("mesh_generation_is_repeatable",data.positions==same.positions and data.normals==same.normals)
	var fine := TileMesh.generate(provider,Location.tile(2,19,(tile.x+1)*2,tile.y*2))
	var seam_match := true
	for y in range(17):
		var a: Vector3=data.positions[y*33+32]; var b: Vector3=fine.positions[(y*2)*33]
		var world_a := PackedFloat64Array([data.centre[0]+a.x,data.centre[1]+a.y,data.centre[2]+a.z])
		var world_b := PackedFloat64Array([fine.centre[0]+b.x,fine.centre[1]+b.y,fine.centre[2]+b.z])
		seam_match=seam_match and Location.distance(world_a,world_b)<0.00001
	check("coarse_fine_edge_vertices_share_canonical_surface",seam_match)
	var scan_phase := true
	for y in range(17):
		var delta: Vector2=(data.uvs[y*33+32]-fine.uvs[(y*2)*33])*2.0
		for width in [2.0,1.3,1.8,3.0,26.0,18.0]:
			for component in [delta.x,delta.y]:
				var phase := fposmod(component,width)
				scan_phase=scan_phase and minf(phase,width-phase)<0.0001
	check("scan_layer_and_moss_phase_match_across_tile_lod_seams",scan_phase)
	check("measured_regions_loaded",provider.regions.size()==2)
	var relief := true
	for region in provider.regions:
		var raw: PackedByteArray=region.data
		for xy in [[128,300],[2048,2048],[3700,3300]]:
			var sample: PackedFloat64Array=provider._region_sample(region,(xy[0]+0.5)/4096.0,(xy[1]+0.5)/4096.0)
			var expected: float=float(raw.decode_u16((xy[1]*4096+xy[0])*2))/65535.0*(float(region.height_max_m)-float(region.height_min_m))+float(region.height_min_m)+float(region.height_offset_m)
			relief=relief and absf(sample[0]-expected)<1e-8
	check("regional_samples_preserve_physical_relief",relief)
	var folder := ProjectSettings.globalize_path("user://native-core-test"); DirAccess.make_dir_recursive_absolute(folder)
	var job := Job.new(); job.provider=provider; job.tile=tile; job.cache_path=folder+"/test.opdc"
	if FileAccess.file_exists(job.cache_path): DirAccess.remove_absolute(job.cache_path)
	var id := WorkerThreadPool.add_task(job.run)
	while not WorkerThreadPool.is_task_completed(id): await process_frame
	WorkerThreadPool.wait_for_task_completion(id)
	var cached := Job.new(); cached.provider=provider; cached.tile=tile; cached.cache_path=job.cache_path; cached.run()
	check("worker_and_cache_match_canonical_mesh",cached.cache_hit and cached.result.positions==data.positions)
	var corrupt := FileAccess.open(job.cache_path,FileAccess.WRITE); corrupt.store_string("broken"); corrupt.close(); cached.run()
	check("corrupt_cache_detected_and_regenerated",cached.corrupt_cache and cached.result.positions==data.positions)
	var eco := CellJob.new(); eco.provider=provider; eco.tile=Location.tile(2,17,70778,72744); eco.tile.key+="/trees"
	var a := eco.generate(); var b := eco.generate()
	check("ecology_ids_transforms_stable_on_revisit",a.records.size()>0 and a.records==b.records and a.ids==b.ids)
	check("ecology_ids_unique_in_cell",a.ids.size()==Array(a.ids).reduce(func(acc: Dictionary,key: String): acc[key]=true; return acc,{}).size())
	settings.tree_reach_m=80; settings.scatter_triangle_budget=100000
	var unchanged := eco.generate()
	check("quality_changes_preserve_ecology_candidates",a.ids==unchanged.ids and a.records==unchanged.records)
	var dense := CellJob.new(); dense.provider=provider; dense.ground=true
	dense.tile=Location.tile(2,17,70778,72744); dense.tile.key+="/ground"
	dense.cache_path=folder+"/dense-ground.opdc"
	if FileAccess.file_exists(dense.cache_path): DirAccess.remove_absolute(dense.cache_path)
	dense.run(); var dense_ids: PackedStringArray=dense.result.ids.duplicate()
	var dense_bytes := FileAccess.get_file_as_bytes(dense.cache_path).size()
	dense.run()
	check("dense_ground_cell_cache_survives_large_payload",dense.cache_hit and not dense.corrupt_cache and dense_bytes>1000000 and dense.result.ids==dense_ids)
	var other_settings := Definition.new(); other_settings.seed=43
	var other_provider := Provider.new(); other_provider.configure(other_settings)
	check("seed_change_invalidates_provider_identity",other_provider.signature!=provider.signature and other_provider.identity_namespace!=provider.identity_namespace and absf(other_provider.height(Location.direction(2,0.08,0.11))-provider.height(Location.direction(2,0.08,0.11)))>0.01)
	var cache_root := ProjectSettings.globalize_path("user://native-cache-prune-test"); var cache_revision := cache_root+"/"+"unit".sha256_text()
	DirAccess.make_dir_recursive_absolute(cache_revision)
	for i in 3:
		var entry := FileAccess.open(cache_revision+"/"+str(i)+".opdc",FileAccess.WRITE); entry.store_buffer("1234567890".to_ascii_buffer()); entry.close()
	var keep := FileAccess.open(cache_revision+"/keep.txt",FileAccess.WRITE); keep.store_string("keep"); keep.close()
	var remaining := DiskCache.prune(cache_root,15)
	check("disk_lru_bound_preserves_unrelated_files",remaining<=15 and FileAccess.file_exists(cache_revision+"/keep.txt"))
	var report := {"checks":checks,"passed":not failed,"count":checks.size(),"engine":Engine.get_version_info(),"provider_signature":provider.signature}
	var path := "user://native-core-checks.json"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): path=arg.trim_prefix("--report=")
	var file := FileAccess.open(path,FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	print("OPD_NATIVE_CORE ",JSON.stringify(report)); quit(1 if failed else 0)
