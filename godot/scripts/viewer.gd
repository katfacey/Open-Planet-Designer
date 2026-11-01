# SPDX-License-Identifier: GPL-3.0-or-later
extends Node3D

const Data = preload("res://scripts/import_data.gd")
const ASSETS := "res://assets/generated/"
const SITES := ["Forest", "Grassland", "Alpine", "Desert", "Ocean"]
const TREES := ["TREE", "TREE_B", "TREE_C", "SAPLING", "SAPLING_B", "FIR", "DEAD"]

var manifest: Dictionary
var site_data: Dictionary
var active_site := "Forest"
var content: Node3D
var camera: Camera3D
var sun: DirectionalLight3D
var world: WorldEnvironment
var sky_material: PhysicalSkyMaterial
var status: Label
var stats: Label
var help: Label
var hud: CanvasLayer
var mesh_cache := {}
var batch_nodes: Array[GeometryInstance3D] = []
var chunk_nodes: Array[MeshInstance3D] = []
var decoder: Thread
var loading := false
var smoke := false
var screenshot_path := ""
var report_path := "user://godot-import-check.json"
var save_scene := false
var force_raw := false
var lifecycle := false
var load_seconds := 0.0
var speed := 6.0
var yaw := 0.0
var pitch := 0.0
var global_x := 0.0
var global_y := 0.0
var global_z := 0.0
var origin_x := 0.0
var origin_y := 0.0
var origin_z := 0.0
var imported_instances := 0
var terrain_triangles := 0
var batch_count := 0
var frame_times := PackedFloat64Array()
var vegetation_visible := true
var tree_reach := 1200.0
var ground_reach := 100.0
var last_frame_us := 0

func _ready() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument == "--smoke": smoke = true
		elif argument.begins_with("--site="): active_site = argument.get_slice("=", 1)
		elif argument.begins_with("--screenshot="): screenshot_path = argument.trim_prefix("--screenshot=")
		elif argument.begins_with("--report="): report_path = argument.trim_prefix("--report=")
		elif argument=="--save-scene": save_scene=true; force_raw=true
		elif argument=="--raw": force_raw=true
		elif argument=="--lifecycle": lifecycle=true
	if smoke: get_window().position = Vector2i(-5000, -5000)
	_build_viewer()
	if not FileAccess.file_exists(ASSETS + "manifest.json"):
		status.text = "Assets are missing. Run tools/export_godot.py in Blender first."
		if smoke: get_tree().quit(2)
		return
	manifest = JSON.parse_string(FileAccess.get_file_as_string(ASSETS + "manifest.json"))
	await load_site(active_site)
	if lifecycle: await _lifecycle_finish()
	elif smoke: await _smoke_finish()

func _build_viewer() -> void:
	content = Node3D.new(); content.name = "ImportedBlenderContent"; add_child(content)
	camera = Camera3D.new(); camera.name = "FreeFlightCamera"; camera.near = 0.2; camera.far = 20000.0
	camera.fov = 60.0; camera.current = true; add_child(camera)
	sun = DirectionalLight3D.new(); sun.name = "ImportedSunDirection"; sun.light_energy = 1.6
	sun.shadow_enabled = true; sun.directional_shadow_max_distance = 250.0
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	add_child(sun)
	world = WorldEnvironment.new(); world.name="ImportedWorldEnvironment"; var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	var sky := Sky.new(); sky_material = PhysicalSkyMaterial.new()
	sky_material.rayleigh_coefficient = 2.0; sky_material.mie_coefficient = 0.005
	sky.sky_material = sky_material; environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.ambient_light_energy = 0.6
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	environment.ssao_enabled = true
	environment.ssao_radius = 1.5; environment.ssao_intensity = 1.0
	environment.fog_enabled = false
	world.environment = environment; add_child(world)
	hud = CanvasLayer.new(); add_child(hud)
	var panel := PanelContainer.new(); panel.position = Vector2(12,12); hud.add_child(panel)
	var margin := MarginContainer.new(); panel.add_child(margin)
	for side in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+side,12)
	var box := VBoxContainer.new(); margin.add_child(box)
	var title := Label.new(); title.text = "OPEN PLANET DESIGNER · GODOT IMPORT"; box.add_child(title)
	status = Label.new(); status.text = "Loading Blender export…"; box.add_child(status)
	stats = Label.new(); box.add_child(stats)
	help = Label.new()
	help.text = "Hold RMB + mouse to look · WASD move · E/Q up/down · Shift boost\nWheel changes speed · 1–5 review locations · Home reset · O globe preview\nV vegetation · H interface · Esc releases mouse\nFrozen Blender coverage: moving beyond it does not generate new detail."
	box.add_child(help)
	var row := HBoxContainer.new(); box.add_child(row)
	for site in SITES:
		var button := Button.new(); button.text = site
		button.pressed.connect(load_site.bind(site))
		row.add_child(button)
	var settings := HBoxContainer.new(); box.add_child(settings)
	for setting in [["Trees (m)",1200.0,50.0,4000.0],["Ground cover (m)",100.0,10.0,500.0]]:
		var caption := Label.new(); caption.text=setting[0]; settings.add_child(caption)
		var value := SpinBox.new(); value.min_value=setting[2]; value.max_value=setting[3]
		value.step=10.0; value.value=setting[1]; settings.add_child(value)
		var trees: bool=setting[0]=="Trees (m)"
		value.value_changed.connect(func(distance: float): _set_reach(trees,distance))

func _set_reach(trees: bool,distance: float) -> void:
	if trees: tree_reach=distance
	else: ground_reach=distance
	for batch in batch_nodes:
		if bool(batch.get_meta("is_tree",false))==trees:
			var begin: float=float(batch.get_meta("nominal_begin",batch.visibility_range_begin))
			var end: float=min(float(batch.get_meta("nominal_end",batch.visibility_range_end)),distance)
			batch.visibility_range_end=max(begin+0.01,end)
			batch.visible=vegetation_visible and distance>begin

func _ground_material(site: String) -> ShaderMaterial:
	var material := ShaderMaterial.new(); material.shader = load("res://shaders/ground.gdshader")
	var prefixes := ["meadow","litter","mud","rock"]
	var scans := ["leafy_grass","forrest_ground_01","brown_mud_leaves_01","rock_boulder_dry"]
	for i in 4:
		for channel in ["color","roughness","height"]:
			var suffix := ".jpg" if channel == "color" else ".png"
			var key: String = prefixes[i] + "_" + ("rough" if channel == "roughness" else channel)
			material.set_shader_parameter(key,load(ASSETS + "scans/" + scans[i] + "_" + channel + suffix))
	material.set_shader_parameter("moisture",float(site_data.get("ground_moisture",0.35)))
	material.set_shader_parameter("alpine",site == "Alpine")
	return material

func _decode_site(data: Dictionary) -> Array:
	# Only file reads and packed CPU arrays on this worker. No scene or GPU resources.
	var decoded := []
	for chunk in data["terrain"]:
		decoded.append({"info":chunk,"arrays":Data.read_terrain(chunk["file"])})
	return decoded

func load_site(site: String) -> void:
	if loading or not manifest["sites"].has(site): return
	loading = true; var start := Time.get_ticks_usec()
	status.text = "Loading " + site + "…"
	if not force_raw and FileAccess.file_exists(ASSETS+site.to_lower()+"_review.scn"):
		await _load_editable_scene(site,start)
		return
	var next_data: Dictionary = manifest["sites"][site]
	decoder = Thread.new(); decoder.start(_decode_site.bind(next_data))
	# Import models using Godot's resource loader while CPU terrain decoding proceeds.
	for record in next_data["instances"]:
		var key: String = record["prototype"]
		var kind: String = record["kind"]
		for level in range(int(record["level"]),3):
			var lod_key := kind + "_" + str(level)
			if mesh_cache.has(lod_key): continue
			var path: String = ASSETS + manifest["prototypes"][lod_key]["file"]
			ResourceLoader.load_threaded_request(path)
			while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				await get_tree().process_frame
			var packed := ResourceLoader.load_threaded_get(path) as PackedScene
			if packed == null:
				push_error("Could not load " + path); continue
			var root := packed.instantiate()
			var instance := _find_mesh(root)
			if instance != null:
				var mesh := instance.mesh.duplicate() as ArrayMesh
				for surface in mesh.get_surface_count():
					# glTF may put vertex-color/PBR variants on the node, not its shared mesh.
					var mat := instance.get_active_material(surface)
					if mat is StandardMaterial3D:
						mat = mat.duplicate()
						if kind=="GRASS": mat.vertex_color_use_as_albedo=true
						if mat.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
							mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
							mat.alpha_scissor_threshold = 0.3
							mat.cull_mode = BaseMaterial3D.CULL_DISABLED
						mesh.surface_set_material(surface,mat)
				mesh_cache[lod_key] = mesh
			root.free()
			await get_tree().process_frame
	while decoder.is_alive(): await get_tree().process_frame
	var decoded: Array = decoder.wait_to_finish(); decoder = null
	for child in content.get_children(): child.queue_free()
	await get_tree().process_frame
	chunk_nodes.clear(); batch_nodes.clear(); terrain_triangles = 0; imported_instances = 0; batch_count = 0
	active_site = site; site_data = next_data; _reset_camera()
	var material := _ground_material(site)
	for i in decoded.size():
		var entry: Dictionary = decoded[i]
		if entry["arrays"].is_empty(): continue
		var mesh := ArrayMesh.new(); mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,entry["arrays"])
		var instance := MeshInstance3D.new(); instance.mesh = mesh; instance.material_override = material
		instance.position = Data.vec(entry["info"]["center"]); instance.name = "BlenderTerrain_" + str(i)
		# Full far globe stays visible but uses no continent-scale shadow frustum.
		if instance.position.length() > 20000.0: instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		content.add_child(instance); chunk_nodes.append(instance)
		terrain_triangles += int(entry["info"]["triangles"])
		if i % 4 == 0:
			status.text = "Uploading " + site + " terrain " + str(i+1) + "/" + str(decoded.size())
			await get_tree().process_frame
	decoded.clear()
	for record in site_data["instances"]:
		var input := Data.read_instances(record["file"])
		if input.is_empty(): continue
		imported_instances += int(input["count"])
		_create_batches(record,input)
		await get_tree().process_frame
	load_seconds = (Time.get_ticks_usec()-start)/1000000.0
	loading = false
	if save_scene: _save_editable_scene()
	_set_reach(true,tree_reach); _set_reach(false,ground_reach)
	status.text = site + " · imported Blender geometry · " + ("%.1f s load" % load_seconds)
	print("GODOT_SITE_READY ",JSON.stringify({"site":site,"instances":imported_instances,"terrain_triangles":terrain_triangles,
		"terrain_chunks":chunk_nodes.size(),"batches":batch_count,"load_seconds":load_seconds}))

func _save_editable_scene() -> void:
	var review := Node3D.new(); review.name=active_site+"BlenderReview"
	for original in [content,camera,sun,world]:
		var copy: Node=original.duplicate()
		review.add_child(copy); _set_owner(copy,review)
	var packed := PackedScene.new()
	var result := packed.pack(review)
	if result==OK:
		result=ResourceSaver.save(packed,ASSETS+active_site.to_lower()+"_review.scn",ResourceSaver.FLAG_COMPRESS)
	print("GODOT_EDITABLE_SCENE ",active_site," result=",result)
	review.free()

func _set_owner(node: Node, owner_root: Node) -> void:
	node.owner=owner_root
	for child in node.get_children(): _set_owner(child,owner_root)

func _load_editable_scene(site: String,start: int) -> void:
	var path := ASSETS+site.to_lower()+"_review.scn"
	var working_scene := "res://scenes/"+site.to_lower()+".tscn"
	if FileAccess.file_exists(working_scene): path=working_scene
	ResourceLoader.load_threaded_request(path)
	while ResourceLoader.load_threaded_get_status(path)==ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
	var packed := ResourceLoader.load_threaded_get(path) as PackedScene
	if packed==null:
		status.text="Could not load editable scene "+site; loading=false; return
	var review := packed.instantiate()
	content.free(); sun.free(); world.free()
	content=review.get_node("ImportedBlenderContent"); review.remove_child(content); _clear_owner(content); add_child(content)
	sun=review.get_node("ImportedSunDirection"); review.remove_child(sun); _clear_owner(sun); add_child(sun)
	world=review.get_node("ImportedWorldEnvironment"); review.remove_child(world); _clear_owner(world); add_child(world)
	var saved_camera: Camera3D=review.get_node("FreeFlightCamera")
	var saved_transform: Transform3D=saved_camera.transform
	var saved_fov: float=saved_camera.fov
	var saved_attributes: CameraAttributes=saved_camera.attributes
	var saved_sun_basis: Basis=sun.basis
	active_site=site; site_data=manifest["sites"][site]; _reset_camera()
	camera.transform=saved_transform
	camera.fov=saved_fov; camera.attributes=saved_attributes
	sun.basis=saved_sun_basis
	global_x=saved_transform.origin.x; global_y=saved_transform.origin.y; global_z=saved_transform.origin.z
	pitch=camera.rotation.x; yaw=camera.rotation.y
	review.free()
	chunk_nodes.clear(); batch_nodes.clear(); _collect_geometry(content)
	_set_reach(true,tree_reach); _set_reach(false,ground_reach)
	batch_count=batch_nodes.size(); imported_instances=0; terrain_triangles=0
	for record in site_data["instances"]: imported_instances+=int(record["count"])
	for chunk in site_data["terrain"]: terrain_triangles+=int(chunk["triangles"])
	load_seconds=(Time.get_ticks_usec()-start)/1000000.0; loading=false
	status.text=site+" · editable Godot scene · "+("%.1f s load" % load_seconds)
	print("GODOT_SITE_READY ",JSON.stringify({"site":site,"instances":imported_instances,
		"terrain_triangles":terrain_triangles,"terrain_chunks":chunk_nodes.size(),"batches":batch_count,"load_seconds":load_seconds,"editable":true}))

func _collect_geometry(node: Node) -> void:
	if node is MultiMeshInstance3D: batch_nodes.append(node)
	elif node is MeshInstance3D: chunk_nodes.append(node)
	for child in node.get_children(): _collect_geometry(child)

func _clear_owner(node: Node) -> void:
	node.owner=null
	for child in node.get_children(): _clear_owner(child)

func _find_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D: return node
	for child in node.get_children():
		var found := _find_mesh(child)
		if found != null: return found
	return null

func _create_batches(record: Dictionary, input: Dictionary) -> void:
	var cells := {}
	var transforms: PackedFloat32Array = input["transforms"]
	var is_tree: bool = record["kind"] in TREES
	var source_level: int=int(record["level"])
	# Small hero batches keep nearby original detail from being culled by a distant cell centre.
	var width: float=float([16.0,32.0,64.0][source_level]) if is_tree else (8.0 if source_level==0 else 16.0)
	for i in int(input["count"]):
		var transform := Data.instance_transform(transforms,i)
		var key := Vector3i(floor(transform.origin.x/width),floor(transform.origin.y/width),floor(transform.origin.z/width))
		if not cells.has(key): cells[key] = []
		cells[key].append(transform)
	for key in cells:
		var centre: Vector3=(Vector3(key)+Vector3(0.5,0.5,0.5))*width
		var base: int = int(record["level"])
		for level in range(base,3):
			var lod_key: String = record["kind"] + "_" + str(level)
			if not mesh_cache.has(lod_key): continue
			var multimesh := MultiMesh.new(); multimesh.transform_format = MultiMesh.TRANSFORM_3D
			multimesh.mesh = mesh_cache[lod_key]; multimesh.instance_count = cells[key].size()
			for i in cells[key].size():
				var transform: Transform3D = cells[key][i]; transform.origin -= centre
				multimesh.set_instance_transform(i,transform)
			var batch := MultiMeshInstance3D.new(); batch.multimesh = multimesh; batch.position = centre
			batch.name = str(record["kind"]) + "_LOD" + str(level)
			var first := 35.0 if is_tree else 12.0
			var second := 180.0 if is_tree else 40.0
			batch.visibility_range_begin = 0.0 if level == base else (first if level == 1 else second)
			batch.visibility_range_end = (first if level == 0 else second) if level < 2 else (tree_reach if is_tree else ground_reach)
			batch.visibility_range_begin_margin = 6.0 if is_tree else 2.0
			batch.visibility_range_end_margin = 6.0 if is_tree else 2.0
			batch.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			batch.set_meta("is_tree",is_tree); batch.set_meta("last_lod",level==2)
			batch.set_meta("source_batch",level==base)
			batch.set_meta("nominal_begin",batch.visibility_range_begin)
			batch.set_meta("nominal_end",1000000000.0 if level==2 else batch.visibility_range_end)
			if level==2: batch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			content.add_child(batch); batch_nodes.append(batch); batch_count += 1

func _reset_camera() -> void:
	global_x=0.0; global_y=0.0; global_z=0.0; origin_x=0.0; origin_y=0.0; origin_z=0.0
	content.position=Vector3.ZERO; camera.position=Vector3.ZERO
	camera.basis=Data.basis(site_data["camera_basis"]).orthonormalized()
	camera.fov=float(site_data.get("camera_fov_deg",35.12))
	var rotation := camera.rotation; pitch=rotation.x; yaw=rotation.y; speed=6.0
	sun.basis=Data.basis(site_data["sun_basis"]).orthonormalized()

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT:
			Input.mouse_mode=Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP: speed=min(speed*1.5,2000000.0)
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN: speed=max(speed/1.5,0.1)
	elif event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
		yaw-=event.relative.x*0.002; pitch=clamp(pitch-event.relative.y*0.002,-1.55,1.55)
		camera.rotation=Vector3(pitch,yaw,0.0)
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_ESCAPE: Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
		elif event.keycode==KEY_F1: get_tree().change_scene_to_file("res://runtime.tscn")
		elif event.keycode>=KEY_1 and event.keycode<=KEY_5 and not loading: load_site(SITES[event.keycode-KEY_1])
		elif event.keycode==KEY_HOME and not loading: _reset_camera()
		elif event.keycode==KEY_O and not loading:
			global_x=0.0; global_y=float(site_data["planet_radius"])*3.2; global_z=0.0
			camera.rotation=Vector3(-PI/2.0,0.0,0.0); pitch=-PI/2.0; yaw=0.0; speed=100000.0
		elif event.keycode==KEY_H: hud.visible=not hud.visible
		elif event.keycode==KEY_V:
			vegetation_visible=not vegetation_visible
			_set_reach(true,tree_reach); _set_reach(false,ground_reach)

func _process(delta: float) -> void:
	if camera==null: return
	if not loading:
		var move := Vector3.ZERO
		if Input.is_physical_key_pressed(KEY_W): move.z-=1.0
		if Input.is_physical_key_pressed(KEY_S): move.z+=1.0
		if Input.is_physical_key_pressed(KEY_A): move.x-=1.0
		if Input.is_physical_key_pressed(KEY_D): move.x+=1.0
		var velocity := camera.basis*move
		if Input.is_physical_key_pressed(KEY_E): velocity.y+=1.0
		if Input.is_physical_key_pressed(KEY_Q): velocity.y-=1.0
		if velocity.length_squared()>0.0:
			velocity=velocity.normalized()*speed*delta*(4.0 if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
			global_x+=velocity.x; global_y+=velocity.y; global_z+=velocity.z
		_update_render_origin()
		var now := Time.get_ticks_usec()
		if last_frame_us>0 and frame_times.size()<4000: frame_times.append((now-last_frame_us)/1000.0)
		last_frame_us=now
	stats.text="%d FPS · %.1f m/s · %s instances · %s terrain triangles\nLOD: original Blender detail near you, cheaper source meshes farther away" % [Engine.get_frames_per_second(),speed,str(imported_instances),str(terrain_triangles)]

func _update_render_origin() -> void:
	# Global scalar positions remain 64-bit; rendered camera stays within a 256 m cell.
	if abs(global_x-origin_x)>256.0 or abs(global_y-origin_y)>256.0 or abs(global_z-origin_z)>256.0:
		origin_x=snapped(global_x,256.0); origin_y=snapped(global_y,256.0); origin_z=snapped(global_z,256.0)
		content.position=-Vector3(origin_x,origin_y,origin_z)
	camera.position=Vector3(global_x-origin_x,global_y-origin_y,global_z-origin_z)
	# CPU light culling also needs a representable far/near projection ratio.
	var radius: float=float(site_data.get("planet_radius",6371000.0))
	var altitude: float=max(global_y,0.0)
	camera.far=max(20000.0,sqrt(altitude*(2.0*radius+altitude))*1.4)
	camera.near=max(0.05,camera.far*0.00001)

func _runtime_checks() -> Dictionary:
	var checks := {}
	var expected := 0
	for entry in site_data["instances"]: expected+=int(entry["count"])
	var actual := 0
	for batch in batch_nodes:
		if batch.get_meta("source_batch",false): actual+=batch.multimesh.instance_count
	checks["all_exported_instances_in_original_lod_batches"]=actual==expected
	checks["all_terrain_chunks_present"]=chunk_nodes.size()==site_data["terrain"].size()
	global_x=987.125; global_y=56.5; global_z=-513.5; _update_render_origin()
	checks["camera_kept_local_after_rebase"]=camera.position.distance_to(Vector3(-36.875,56.5,-1.5))<0.000001
	checks["centimetre_motion_retained"]=abs(((global_x+0.01)-global_x)-0.01)<0.000001
	global_x=0.0; global_y=0.0; global_z=0.0; _update_render_origin()
	checks["return_to_origin_exact"]=camera.position==Vector3.ZERO and content.position==Vector3.ZERO
	checks["stable_projection_ratio"]=camera.far/camera.near<=100001.0
	var saved_tree_reach := tree_reach
	var saved_ground_reach := ground_reach
	for is_tree in [true,false]:
		var limit := 100.0 if is_tree else 20.0
		_set_reach(is_tree,limit)
		var correct := true
		for batch in batch_nodes:
			if bool(batch.get_meta("is_tree",false))==is_tree and batch.visible and batch.visibility_range_end>limit+0.01: correct=false
		checks["tree_distance_limits_all_lods" if is_tree else "ground_distance_limits_all_lods"]=correct
	_set_reach(true,saved_tree_reach); _set_reach(false,saved_ground_reach)
	return checks

func _smoke_finish() -> void:
	var checks := _runtime_checks()
	var deadline := Time.get_ticks_usec()+1000000
	while Time.get_ticks_usec()<deadline: await get_tree().process_frame
	frame_times.clear(); last_frame_us=0
	deadline=Time.get_ticks_usec()+2000000
	while Time.get_ticks_usec()<deadline: await get_tree().process_frame
	if screenshot_path!="":
		hud.visible=false
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(screenshot_path)
		hud.visible=true
	var report := {"site":active_site,"instances":imported_instances,"terrain_triangles":terrain_triangles,
		"chunks":chunk_nodes.size(),"batches":batch_count,"load_seconds":load_seconds,
		"renderer":RenderingServer.get_current_rendering_method(),"gpu":RenderingServer.get_video_adapter_name(),
		"fps_at_capture":Engine.get_frames_per_second(),"frame_samples_ms":Array(frame_times),
		"checks":checks,"errors_are_fatal":true,"scope":"Frozen Blender export; no new procedural terrain generation"}
	var bounds := {}
	for key in mesh_cache:
		var box: AABB=mesh_cache[key].get_aabb()
		bounds[key]=[box.size.x,box.size.y,box.size.z]
	report["prototype_bounds"]=bounds
	var output := FileAccess.open(report_path,FileAccess.WRITE)
	output.store_string(JSON.stringify(report,"\t")); output.close()
	print("GODOT_IMPORT_SMOKE_COMPLETE ",JSON.stringify(report))
	var success := true
	for value in checks.values(): success=success and bool(value)
	get_tree().quit(0 if success else 3)

func _lifecycle_finish() -> void:
	var results := {}; var success := true
	for site in SITES+["Forest"]:
		if active_site!=site: await load_site(site)
		var checks := _runtime_checks()
		for value in checks.values(): success=success and bool(value)
		results[site]={"instances":imported_instances,"terrain_triangles":terrain_triangles,"checks":checks}
		await get_tree().process_frame
	var output := FileAccess.open(report_path,FileAccess.WRITE)
	output.store_string(JSON.stringify(results,"\t")); output.close()
	print("GODOT_LIFECYCLE_COMPLETE ",success)
	get_tree().quit(0 if success else 3)

func _exit_tree() -> void:
	if decoder!=null and decoder.is_started(): decoder.wait_to_finish()
