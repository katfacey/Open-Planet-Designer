# SPDX-License-Identifier: GPL-3.0-or-later
extends Node3D
const Definition=preload("res://scripts/world/planet_definition.gd")
const Location=preload("res://scripts/world/planet_location.gd")
const Provider=preload("res://scripts/terrain/height_provider.gd")
const Terrain=preload("res://scripts/streaming/terrain_stream.gd")
const Recorder=preload("res://scripts/tools/flight_recorder.gd")
const Route=preload("res://scripts/navigation/flight_route.gd")
const Ecosystem=preload("res://scripts/ecology/ecosystem_stream.gd")
const Collision=preload("res://scripts/navigation/collision_bubble.gd")
@export var planet_settings: Resource
var definition: Resource=Definition.new()
var provider := Provider.new()
var terrain := Terrain.new()
var camera: Camera3D
var sun: DirectionalLight3D
var world: WorldEnvironment
var hud: CanvasLayer
var status: Label
var position64 := PackedFloat64Array([0.0,0.0,0.0])
var origin64 := PackedFloat64Array([0.0,0.0,0.0])
var tangent := Basis.IDENTITY
var yaw: float=0.0
var pitch: float=-0.08
var speed: float=8.0
var clearance: float=0.0
var altitude: float=0.0
var keep_above_ground: bool=true
var profiler := Recorder.new()
var route := Route.new()
var replay: bool=false
var replay_time: float=0.0
var replay_duration: float=60.0
var replay_name: String="woodland"
var profile_path: String="user://latest-flight-profile.json"
var screenshot_path: String=""
var automated: bool=false
var elapsed: float=0.0
var warmup_seconds: float=10.0
var rebase_count: int=0
var ground_material: ShaderMaterial
var finished: bool=false
var ecology := Ecosystem.new()

func _ready() -> void:
	if planet_settings!=null: definition=planet_settings.duplicate(true)
	for arg in OS.get_cmdline_user_args():
		if arg=="--benchmark": automated=true
		elif arg.begins_with("--seconds="): replay_duration=float(arg.trim_prefix("--seconds="))
		elif arg.begins_with("--route="): replay_name=arg.trim_prefix("--route=")
		elif arg.begins_with("--report="): profile_path=arg.trim_prefix("--report=")
		elif arg.begins_with("--screenshot="): screenshot_path=arg.trim_prefix("--screenshot=")
		elif arg.begins_with("--warmup="): warmup_seconds=float(arg.trim_prefix("--warmup="))
		elif arg.begins_with("--cache-namespace="): definition.cache_namespace=arg.trim_prefix("--cache-namespace=")
	if automated: get_window().position=Vector2i(-5000,-5000)
	provider.configure(definition)
	_build_world(); _build_interface()
	ground_material=_make_ground()
	add_child(terrain); terrain.configure(provider,definition,ground_material)
	add_child(ecology); ecology.configure(provider,definition)
	_bookmark(2,0.0798,0.11015,2.2)
	if automated:
		var initial := route_position_for_start()
		position64=initial.position; tangent=Location.frame(initial.direction); pitch=initial.pitch; _camera_transform()
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(),true)
	route.configure(replay_name,replay_duration)
	print("OPD_NATIVE_READY ",JSON.stringify({"provider":provider.signature,"radius_m":definition.radius_m,"regions":provider.regions.size()}))

func route_position_for_start() -> Dictionary:
	route.configure(replay_name,replay_duration)
	return route.position_at(0.0,provider)

func _build_world() -> void:
	camera=Camera3D.new(); camera.name="FreeFlightCamera"; camera.current=true; camera.fov=65.0; camera.near=0.2; camera.far=20000.0; add_child(camera)
	sun=DirectionalLight3D.new(); sun.name="Sun"; sun.rotation_degrees=Vector3(-48.0,-30.0,0.0)
	sun.light_energy=1.7; sun.shadow_enabled=true; sun.directional_shadow_max_distance=definition.shadow_distance_m
	sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS; add_child(sun)
	world=WorldEnvironment.new(); world.name="WorldEnvironment"; world.environment=Environment.new()
	var sky := Sky.new(); var physical := PhysicalSkyMaterial.new()
	physical.rayleigh_coefficient=2.0; physical.mie_coefficient=0.005; sky.sky_material=physical
	world.environment.sky=sky; world.environment.background_mode=Environment.BG_SKY
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_SKY; world.environment.ambient_light_energy=0.7
	world.environment.tonemap_mode=Environment.TONE_MAPPER_AGX
	world.environment.ssao_enabled=true; world.environment.ssao_radius=1.0; add_child(world)

func _make_ground() -> ShaderMaterial:
	var material := ShaderMaterial.new(); material.shader=load("res://shaders/native_ground.gdshader")
	for pair in [["meadow","leafy_grass"],["litter","forrest_ground_01"],["mud","brown_mud_leaves_01"],["rock","rock_boulder_dry"]]:
		for channel in ["color","roughness","height"]:
			var path: String="res://assets/catalog/scans/"+pair[1]+"_"+channel+(".jpg" if channel=="color" else ".png")
			if ResourceLoader.exists(path): material.set_shader_parameter(pair[0]+"_"+("rough" if channel=="roughness" else channel),load(path))
	return material

func _build_interface() -> void:
	hud=CanvasLayer.new(); add_child(hud)
	var panel := PanelContainer.new(); panel.position=Vector2(12,12); hud.add_child(panel)
	var margin := MarginContainer.new(); panel.add_child(margin)
	for side in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+side,10)
	var box := VBoxContainer.new(); margin.add_child(box)
	var title := Label.new(); title.text="OPEN PLANET DESIGNER · NATIVE STREAMING ALPHA"; box.add_child(title)
	status=Label.new(); box.add_child(status)
	var help := Label.new(); help.text="RMB look · WASD fly · E/Q radial up/down · Shift boost · Wheel speed\nHome woodland · O orbit · P route replay · F8 save profile · H interface\nV vegetation · Esc release mouse"+(" · F1 imported references" if ResourceLoader.exists("res://main.tscn") else ""); box.add_child(help)
	var row := HBoxContainer.new(); box.add_child(row)
	for item in [["Forest",2,0.0798,0.11015,2.2],["Meadow",2,0.08,0.11,2.2],["Rainier",2,0.32,0.18,600.0],["Canyon",0,0.05,0.3,500.0],["Pole",2,0.0,0.0,2000.0]]:
		var button := Button.new(); button.text=item[0]; row.add_child(button)
		button.pressed.connect(_bookmark.bind(item[1],item[2],item[3],item[4]))
	var check := CheckBox.new(); check.text="Terrain clearance + nearby trunk/rock collision"; check.button_pressed=true; box.add_child(check)
	check.toggled.connect(func(value: bool): keep_above_ground=value)
	for item in [["Terrain error (px)",definition.terrain_pixels,1.0,20.0],["Trees (m)",definition.tree_reach_m,50.0,1000.0],["Ground cover (m)",definition.ground_reach_m,10.0,100.0]]:
		var line := HBoxContainer.new(); box.add_child(line)
		var label := Label.new(); label.text=item[0]; line.add_child(label)
		var field := SpinBox.new(); field.min_value=item[2]; field.max_value=item[3]; field.value=item[1]; line.add_child(field)
		var name: String=item[0]
		field.value_changed.connect(func(value: float):
			if name=="Terrain error (px)": definition.terrain_pixels=value; terrain.force_selection()
			elif name=="Trees (m)": definition.tree_reach_m=value
			else: definition.ground_reach_m=value)
	var advanced := CheckButton.new(); advanced.text="Detail budgets"; box.add_child(advanced)
	var details := VBoxContainer.new(); details.visible=false; box.add_child(details)
	advanced.toggled.connect(func(value: bool): details.visible=value)
	for setting in [["Tree full detail (m)","tree_full_detail_m",1.0,50.0],["Tree medium detail (m)","tree_medium_detail_m",10.0,200.0],["Cover full detail (m)","cover_full_detail_m",1.0,30.0],["Cover medium detail (m)","cover_medium_detail_m",5.0,100.0],["Terrain tile budget","leaf_budget",32.0,384.0],["Scatter triangle budget","scatter_triangle_budget",100000.0,20000000.0],["Instance budget","instance_budget",1000.0,50000.0],["Disk terrain cache (MB)","disk_cache_mb",8.0,512.0],["Shadow reach (m)","shadow_distance_m",20.0,500.0]]:
		var line := HBoxContainer.new(); details.add_child(line)
		var label := Label.new(); label.text=setting[0]; line.add_child(label)
		var field := SpinBox.new(); field.min_value=setting[2]; field.max_value=setting[3]; field.value=float(definition.get(setting[1])); line.add_child(field)
		var property: String=setting[1]
		field.value_changed.connect(func(value: float):
			definition.set(property,int(value) if property in ["leaf_budget","disk_cache_mb","scatter_triangle_budget","instance_budget"] else value)
			if property=="shadow_distance_m": sun.directional_shadow_max_distance=value
			terrain.force_selection())
	var ao := CheckBox.new(); ao.text="Screen-space ambient occlusion"; ao.button_pressed=true; details.add_child(ao)
	ao.toggled.connect(func(value: bool): world.environment.ssao_enabled=value)

func _bookmark(face: int,u: float,v: float,height: float) -> void:
	var d := Location.direction(face,u,v)
	position64=Location.point(d,definition.radius_m+provider.height(d)+height)
	tangent=Location.frame(d); yaw=0.0; pitch=-0.08 if height<10.0 else -0.5
	replay=false; terrain.force_selection(); _camera_transform()

func _input(event: InputEvent) -> void:
	if automated: return
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT: Input.mouse_mode=Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP: speed=minf(speed*1.5,2000000.0)
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN: speed=maxf(speed/1.5,0.1)
	elif event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
		yaw-=event.relative.x*0.002; pitch=clampf(pitch-event.relative.y*0.002,-1.55,1.55); replay=false
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_ESCAPE: Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
			KEY_HOME: _bookmark(2,0.0798,0.11015,2.2)
			KEY_O: _bookmark(2,0.08,0.11,2500000.0); speed=100000.0; pitch=-1.55
			KEY_H: hud.visible=not hud.visible
			KEY_P: replay=not replay; replay_time=0.0; route.configure("woodland",60.0)
			KEY_F8: _save_profile()
			KEY_V: ecology.enabled=not ecology.enabled
			KEY_F1:
				if ResourceLoader.exists("res://main.tscn"): get_tree().change_scene_to_file("res://main.tscn")

func _process(delta: float) -> void:
	if finished: return
	var update_start := Time.get_ticks_usec()
	elapsed+=delta
	if automated and elapsed>=warmup_seconds and not replay:
		replay=true; replay_time=0.0
	if replay:
		replay_time+=delta
		var view := route.position_at(replay_time,provider)
		position64=view.position; tangent=Location.frame(view.direction); pitch=view.pitch; yaw=0.0
	elif not automated:
		var move := Vector3.ZERO
		if Input.is_physical_key_pressed(KEY_W): move.z-=1.0
		if Input.is_physical_key_pressed(KEY_S): move.z+=1.0
		if Input.is_physical_key_pressed(KEY_A): move.x-=1.0
		if Input.is_physical_key_pressed(KEY_D): move.x+=1.0
		var velocity := camera.basis*move
		if Input.is_physical_key_pressed(KEY_E): velocity+=tangent.y
		if Input.is_physical_key_pressed(KEY_Q): velocity-=tangent.y
		if velocity.length_squared()>0.0:
			velocity=velocity.normalized()*speed*delta*(4.0 if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
			var target := PackedFloat64Array([position64[0]+velocity.x,position64[1]+velocity.y,position64[2]+velocity.z])
			position64=Collision.sweep(position64,target,ecology.cells.values()) if keep_above_ground else target
	_camera_transform()
	var focal := float(get_window().size.y)/(2.0*tan(deg_to_rad(camera.fov)*0.5))
	terrain.tick(delta,position64,focal)
	ecology.tick(delta,position64)
	var metrics := terrain.statistics()
	metrics.merge(ecology.statistics())
	profiler.sample(get_viewport(),metrics,{"altitude_m":altitude,"clearance_m":clearance,"rebases":rebase_count,"route_s":replay_time,
		"phase":"warmup" if automated and not replay else "flight","runtime_update_ms":(Time.get_ticks_usec()-update_start)/1000.0})
	status.text="%d FPS · %.1f m/s · %.1f m above terrain\n%d active / %d resident tiles · %d terrain jobs · %d plants / rocks\nTerrain target %.1f px · estimated demand %.1f px\nAtmosphere, clouds, water optics and photographic calibration remain in development." % [Engine.get_frames_per_second(),speed,clearance,metrics.active_tiles,metrics.resident_tiles,metrics.pending_workers,metrics.vegetation_instances,definition.terrain_pixels,metrics.unmet_error_pixels]
	if automated and replay_time>=replay_duration: _finish_automated()

func _camera_transform() -> void:
	var d := Location.normalized(position64)
	altitude=Location.radius(position64)-definition.radius_m
	clearance=altitude-provider.height(d)
	if keep_above_ground and clearance<1.6:
		position64=Location.point(d,definition.radius_m+provider.height(d)+1.6); clearance=1.6
	var up := Vector3(d[0],d[1],d[2]).normalized()
	if tangent.y.dot(up)>-0.9999: tangent=Basis(Quaternion(tangent.y,up))*tangent
	else: tangent=Location.frame(d)
	camera.basis=tangent*Basis.from_euler(Vector3(pitch,yaw,0.0))
	if Location.distance(position64,origin64)>256.0:
		origin64=PackedFloat64Array([snappedf(position64[0],256.0),snappedf(position64[1],256.0),snappedf(position64[2],256.0)])
		terrain.set_origin(origin64); ecology.set_origin(origin64); rebase_count+=1
	camera.position=Location.local(position64,origin64)
	camera.far=maxf(20000.0,sqrt(maxf(altitude,0.0)*(2.0*definition.radius_m+maxf(altitude,0.0)))*1.4)
	camera.near=maxf(0.05,camera.far*0.00001)

func _save_profile() -> void:
	profiler.report(profile_path,{"route":route.name,"provider_signature":provider.signature,"seed":definition.seed,"radius_m":definition.radius_m,
		"scope":"Native streaming alpha; no consumer GPU qualification","cache_namespace":definition.cache_namespace,"stream":terrain.statistics(),"ecosystem":ecology.statistics(),"rebases":rebase_count})

func _finish_automated() -> void:
	finished=true
	_save_profile()
	if not screenshot_path.is_empty():
		hud.visible=false; await get_tree().process_frame; await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(screenshot_path)
	get_tree().quit()

func _exit_tree() -> void:
	terrain.shutdown()
	ecology.shutdown()
