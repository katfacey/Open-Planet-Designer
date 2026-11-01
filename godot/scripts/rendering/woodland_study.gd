# SPDX-License-Identifier: GPL-3.0-or-later
extends Node3D
## A fixed local reference isolates look development from streamed LOD changes.
var look: Resource=preload("res://earth_woodland.tres")
var camera: Camera3D
var sun: DirectionalLight3D
var world: WorldEnvironment
var content: Node3D
var hud: CanvasLayer
var status: Label
var ready_for_capture: bool=false
var yaw: float=0.0
var pitch: float=0.0
var speed: float=3.0
var clearance: bool=true
var default_pose := Transform3D.IDENTITY
var default_sun := Basis.IDENTITY
var lighting: String="daylight"
var gi_enabled: bool=true
var automated_capture: bool=false
var capture_seconds: float=20.0
var capture_image: String=""
var capture_report: String=""

func _ready() -> void:
	if "--benchmark" in OS.get_cmdline_user_args():
		get_tree().call_deferred("change_scene_to_file","res://runtime.tscn"); return
	get_tree().auto_accept_quit=false
	get_window().close_requested.connect(_request_close)
	for arg in OS.get_cmdline_user_args():
		if arg=="--study-capture": automated_capture=true
		elif arg.begins_with("--seconds="): capture_seconds=float(arg.trim_prefix("--seconds="))
		elif arg.begins_with("--screenshot="): capture_image=arg.trim_prefix("--screenshot=")
		elif arg.begins_with("--report="): capture_report=arg.trim_prefix("--report=")
	if automated_capture: get_window().position=Vector2i(-5000,-5000)
	get_window().title="Open Planet Designer · Earth Woodland Study"
	hud=CanvasLayer.new(); add_child(hud)
	var loading := Label.new(); loading.text="Loading Earth woodland visual study…"; loading.position=Vector2(20,20); hud.add_child(loading)
	var path := "res://assets/appearance/forest_study.scn"
	if not ResourceLoader.exists(path):
		loading.text="Study data missing. Run the woodland preparation tools, or press F2 for the native planet."; return
	ResourceLoader.load_threaded_request(path)
	while ResourceLoader.load_threaded_get_status(path)==ResourceLoader.THREAD_LOAD_IN_PROGRESS: await get_tree().process_frame
	var packed := ResourceLoader.load_threaded_get(path) as PackedScene
	if packed==null: push_error("Cannot load woodland study"); return
	content=packed.instantiate(); add_child(content)
	camera=Camera3D.new(); camera.name="StudyCamera"; camera.current=true; camera.near=0.1; camera.far=10000.0; add_child(camera)
	camera.basis=_basis(content.get_meta("camera_basis")); camera.fov=float(content.get_meta("camera_fov")); default_pose=camera.transform
	yaw=camera.rotation.y; pitch=camera.rotation.x
	sun=DirectionalLight3D.new(); sun.name="Daylight"; sun.basis=_basis(content.get_meta("sun_basis")); sun.shadow_enabled=true
	sun.directional_shadow_max_distance=220.0; sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS; add_child(sun); default_sun=sun.basis
	world=WorldEnvironment.new(); world.environment=Environment.new(); add_child(world)
	apply_look(); loading.queue_free(); _interface(); ready_for_capture=true
	print("OPD_WOODLAND_READY ",JSON.stringify({"instances":content.get_meta("instances"),"terrain_triangles":content.get_meta("terrain_triangles"),"scatter_triangles":content.get_meta("scatter_triangles")}))
	if automated_capture: _capture()

func _basis(values: Array) -> Basis:
	return Basis(Vector3(values[0],values[1],values[2]),Vector3(values[3],values[4],values[5]),Vector3(values[6],values[7],values[8])).orthonormalized()

func apply_look() -> void:
	var fov := camera.fov
	look.apply(world.environment,sun,camera)
	sun.light_energy=look.sun_energy*1.4
	camera.fov=fov; sun.basis=default_sun
	if lighting=="backlight": sun.rotate_y(PI)
	elif lighting=="overcast": sun.light_energy=0.25; world.environment.ambient_light_energy=0.65
	set_gi(gi_enabled)

func set_gi(enabled: bool) -> void:
	gi_enabled=enabled
	world.environment.sdfgi_enabled=enabled
	world.environment.sdfgi_cascades=4; world.environment.sdfgi_min_cell_size=0.8
	world.environment.sdfgi_use_occlusion=true; world.environment.sdfgi_bounce_feedback=0.35
	world.environment.sdfgi_energy=1.25
	world.environment.ambient_light_energy=0.55 if enabled else 0.35
	world.environment.tonemap_exposure=look.exposure*(1.15 if enabled else 1.0)
	world.environment.ssil_enabled=look.ssil and not enabled

func _interface() -> void:
	var panel := PanelContainer.new(); panel.position=Vector2(12,12); hud.add_child(panel)
	var margin := MarginContainer.new(); panel.add_child(margin)
	for side in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+side,10)
	var box := VBoxContainer.new(); margin.add_child(box)
	var title := Label.new(); title.text="OPEN PLANET DESIGNER · EARTH WOODLAND STUDY"; box.add_child(title)
	var scope := Label.new(); scope.text="Original Blender forest layout · local visual benchmark\nFixed source detail; the native planet is a separate mode."; box.add_child(scope)
	var help := Label.new(); help.text="RMB look · WASD fly · Q/E down/up · Shift boost · Wheel speed\nHome reset · H interface · F2 native planet · Esc release mouse"; box.add_child(help)
	var lighting_choice := OptionButton.new()
	for label in ["Natural daylight · subtle cinema","Backlight study","Diffuse-light study"]: lighting_choice.add_item(label)
	box.add_child(lighting_choice)
	lighting_choice.item_selected.connect(func(index: int): lighting=["daylight","backlight","overcast"][index]; apply_look())
	var bounced := CheckBox.new(); bounced.text="Local bounced lighting"; bounced.button_pressed=gi_enabled; box.add_child(bounced); bounced.toggled.connect(set_gi)
	var exposure_row := HBoxContainer.new(); box.add_child(exposure_row)
	var exposure_label := Label.new(); exposure_label.text="Exposure"; exposure_row.add_child(exposure_label)
	var exposure_field := SpinBox.new(); exposure_field.min_value=0.5; exposure_field.max_value=2.0; exposure_field.step=0.05
	exposure_field.value=world.environment.tonemap_exposure; exposure_row.add_child(exposure_field)
	exposure_field.value_changed.connect(func(value: float): world.environment.tonemap_exposure=value)
	var terrain_check := CheckBox.new(); terrain_check.text="Keep camera above terrain"; terrain_check.button_pressed=true; box.add_child(terrain_check)
	terrain_check.toggled.connect(func(value: bool): clearance=value)
	var row := HBoxContainer.new(); box.add_child(row)
	var reset := Button.new(); reset.text="Reset view"; row.add_child(reset); reset.pressed.connect(reset_view)
	var native := Button.new(); native.text="Explore native planet"; row.add_child(native); native.pressed.connect(func(): get_tree().change_scene_to_file("res://runtime.tscn"))
	status=Label.new(); box.add_child(status)

func reset_view() -> void:
	camera.transform=default_pose; yaw=camera.rotation.y; pitch=camera.rotation.x

func _input(event: InputEvent) -> void:
	if automated_capture: return
	if event is InputEventKey and event.pressed and event.keycode==KEY_F2:
		get_tree().change_scene_to_file("res://runtime.tscn"); return
	if not ready_for_capture: return
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT: Input.mouse_mode=Input.MOUSE_MODE_CAPTURED if event.pressed else Input.MOUSE_MODE_VISIBLE
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP: speed=minf(100.0,speed*1.4)
		elif event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN: speed=maxf(0.1,speed/1.4)
	elif event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
		yaw-=event.relative.x*0.002; pitch=clampf(pitch-event.relative.y*0.002,-1.5,1.5); camera.rotation=Vector3(pitch,yaw,0)
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_ESCAPE: Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
		elif event.keycode==KEY_HOME: reset_view()
		elif event.keycode==KEY_H: hud.visible=not hud.visible

func _physics_process(delta: float) -> void:
	if not ready_for_capture: return
	if automated_capture: return
	var move := Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),0,float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W)))
	var velocity := camera.basis*move
	velocity.y+=float(Input.is_physical_key_pressed(KEY_E))-float(Input.is_physical_key_pressed(KEY_Q))
	if velocity.length_squared()>0.0:
		camera.position+=velocity.normalized()*speed*delta*(4.0 if Input.is_physical_key_pressed(KEY_SHIFT) else 1.0)
		if clearance:
			var query := PhysicsRayQueryParameters3D.create(camera.position+Vector3.UP*20,camera.position-Vector3.UP*40)
			var hit := get_world_3d().direct_space_state.intersect_ray(query)
			if not hit.is_empty(): camera.position.y=maxf(camera.position.y,hit.position.y+1.65)
	status.text="%d FPS · %.1f m/s · H hides controls" % [Engine.get_frames_per_second(),speed]

func _capture() -> void:
	await get_tree().create_timer(capture_seconds).timeout
	hud.visible=false
	await RenderingServer.frame_post_draw
	var screenshot := get_viewport().get_texture().get_image()
	if not capture_image.is_empty(): screenshot.save_png(capture_image)
	var report := {"mode":"woodland-study","source_sha256":content.get_meta("source_sha256"),"instances":content.get_meta("instances"),"terrain_triangles":content.get_meta("terrain_triangles"),"scatter_triangles":content.get_meta("scatter_triangles"),"sdfgi":gi_enabled,"resolution":[screenshot.get_width(),screenshot.get_height()],"fps_at_capture":Engine.get_frames_per_second(),"fov":camera.fov}
	if not capture_report.is_empty():
		var file := FileAccess.open(capture_report,FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	print("OPD_STUDY_CAPTURE ",JSON.stringify(report))
	var tree := get_tree()
	tree.create_timer(0.25).timeout.connect(tree.quit)
	queue_free()

func _request_close() -> void:
	var tree := get_tree()
	tree.create_timer(0.25).timeout.connect(tree.quit)
	queue_free()
