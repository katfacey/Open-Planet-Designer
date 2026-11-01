# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
var output_folder: String
var scene: Node3D
var camera: Camera3D
var environment: Environment
var overlay: MeshInstance3D

func _initialize() -> void:
	output_folder=ProjectSettings.globalize_path("user://risk-probes")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="): output_folder=arg.trim_prefix("--output=")
	DirAccess.make_dir_recursive_absolute(output_folder)
	root.position=Vector2i(-5000,-5000); root.size=Vector2i(960,540); root.use_taa=false
	_run.call_deferred()

func _run() -> void:
	scene=Node3D.new(); root.add_child(scene)
	camera=Camera3D.new(); camera.current=true; camera.position=Vector3(0,2,7); camera.far=500.0; camera.near=0.2; scene.add_child(camera)
	camera.look_at(Vector3(0,5,-10),Vector3.UP)
	var light := DirectionalLight3D.new(); light.rotation_degrees=Vector3(-45,-30,0); light.light_energy=1.7; light.shadow_enabled=true; scene.add_child(light)
	var world := WorldEnvironment.new(); environment=Environment.new(); world.environment=environment
	var sky := Sky.new(); sky.sky_material=PhysicalSkyMaterial.new(); environment.sky=sky; environment.background_mode=Environment.BG_SKY
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_SKY; environment.ambient_light_energy=0.7; environment.tonemap_mode=Environment.TONE_MAPPER_AGX
	scene.add_child(world)
	var ground := MeshInstance3D.new(); var plane := PlaneMesh.new(); plane.size=Vector2(150,150); ground.mesh=plane
	var soil := StandardMaterial3D.new(); soil.albedo_color=Color(0.2,0.22,0.16); soil.roughness=0.9; ground.material_override=soil
	ground.gi_mode=GeometryInstance3D.GI_MODE_STATIC; scene.add_child(ground)
	var water := MeshInstance3D.new(); var surface := PlaneMesh.new(); surface.size=Vector2(6,8); water.mesh=surface; water.position=Vector3(6,0.05,-5)
	var wet := StandardMaterial3D.new(); wet.albedo_color=Color(0.01,0.06,0.1); wet.roughness=0.15; water.material_override=wet; scene.add_child(water)
	var tree: PackedScene=load("res://assets/catalog/models/tree.gltf".replace("tree.gltf","tree_0.gltf"))
	for i in 3:
		var instance := tree.instantiate() as Node3D; instance.scale=Vector3.ONE*(12.0+i*2.0); instance.position=Vector3(i*7-7,0,-9-i*7)
		_set_static(instance); scene.add_child(instance)
	overlay=MeshInstance3D.new(); var quad := QuadMesh.new(); quad.size=Vector2(2,2); overlay.mesh=quad; overlay.extra_cull_margin=100000.0
	var material := ShaderMaterial.new(); material.shader=load("res://shaders/atmosphere_probe.gdshader"); overlay.material_override=material
	overlay.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF; overlay.visible=false; camera.add_child(overlay)
	await _frames(60); await _capture("clear-before")
	overlay.visible=true; await _frames(3); await _capture("depth-air-before")
	_shift_origin(); await _frames(3); await _capture("depth-air-rebased")
	overlay.visible=false
	environment.sdfgi_enabled=true; environment.sdfgi_use_occlusion=true
	await _frames(180); await _capture("sdfgi-before")
	_shift_origin(); await _frames(3); await _capture("sdfgi-rebased-immediate")
	await _frames(120); await _capture("sdfgi-rebased-settled")
	print("OPD_RISK_PROBES_COMPLETE ",output_folder); quit()

func _set_static(node: Node) -> void:
	if node is MeshInstance3D:
		node.gi_mode=GeometryInstance3D.GI_MODE_STATIC
		for index in node.mesh.get_surface_count():
			var material: Material=node.get_active_material(index)
			if material is StandardMaterial3D:
				material=material.duplicate()
				if material.transparency!=BaseMaterial3D.TRANSPARENCY_DISABLED:
					material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR; material.alpha_scissor_threshold=0.3
				node.set_surface_override_material(index,material)
	for child in node.get_children(): _set_static(child)

func _shift_origin() -> void:
	for node in scene.get_children():
		if node is Node3D and not node is WorldEnvironment: node.position-=Vector3(256,0,0)

func _frames(count: int) -> void:
	for i in count: await process_frame

func _capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output_folder+"/"+name+".png")
