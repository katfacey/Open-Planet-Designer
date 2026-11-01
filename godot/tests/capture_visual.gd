# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
const Look=preload("res://scripts/rendering/earth_look.gd")
var mode: String="native"
var lighting: String="daylight"
var output: String="user://visual.png"
var seconds: float=25.0
var view: String="eye"
var gi: bool=false

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mode="): mode=arg.trim_prefix("--mode=")
		elif arg.begins_with("--lighting="): lighting=arg.trim_prefix("--lighting=")
		elif arg.begins_with("--output="): output=arg.trim_prefix("--output=")
		elif arg.begins_with("--settle="): seconds=float(arg.trim_prefix("--settle="))
		elif arg.begins_with("--view="): view=arg.trim_prefix("--view=")
		elif arg=="--gi": gi=true
	root.position=Vector2i(-5000,-5000)
	call_deferred("capture")

func capture() -> void:
	var scene: Node3D
	var camera: Camera3D
	var sun: DirectionalLight3D
	var world: WorldEnvironment
	var profile: Resource=load("res://earth_woodland.tres")
	if mode=="study":
		scene=load("res://woodland_study.tscn").instantiate(); root.add_child(scene)
		while not scene.ready_for_capture: await process_frame
		scene.set_physics_process(false); scene.set_process_input(false)
		camera=scene.camera; sun=scene.sun; world=scene.world; scene.hud.visible=false
		scene.lighting=lighting; scene.apply_look(); scene.set_gi(gi)
		if view=="canopy": camera.position+=Vector3(10,20,10); camera.rotation.x=-0.4
		elif view=="ground": camera.rotation.x=-0.55
	elif mode=="reference":
		scene=load("res://assets/generated/forest_review.scn").instantiate()
		root.add_child(scene)
		camera=scene.get_node("FreeFlightCamera"); camera.current=true
		sun=scene.get_node("ImportedSunDirection"); world=scene.get_node("ImportedWorldEnvironment")
		var original_fov := camera.fov
		profile.apply(world.environment,sun,camera)
		camera.fov=original_fov
		var ground: ShaderMaterial=profile.ground_material(true)
		var meshes := {}
		for node in scene.find_children("*","MeshInstance3D",true,false): node.material_override=ground
		for node in scene.find_children("*","MultiMeshInstance3D",true,false):
			var source: Mesh=node.multimesh.mesh; var key := source.get_instance_id()
			if not meshes.has(key):
				var mesh: ArrayMesh=source.duplicate()
				for surface in mesh.get_surface_count(): mesh.surface_set_material(surface,profile.prepare_material(source.surface_get_material(surface),"GRASS" if node.name.begins_with("GRASS") else ""))
				meshes[key]=mesh
			node.multimesh=node.multimesh.duplicate(); node.multimesh.mesh=meshes[key]
	else:
		scene=load("res://runtime.tscn").instantiate(); root.add_child(scene)
		scene.automated=true; scene.warmup_seconds=1000000000.0
		camera=scene.camera; sun=scene.sun; world=scene.world
		scene.hud.visible=false
		if view=="canopy": scene._bookmark(2,0.0798,0.11015,32.0)
		elif view=="ground": scene.pitch=-0.62
		elif view=="meadow": scene._bookmark(2,0.08,0.11,2.2)
	if mode!="study":
		if lighting=="overcast": sun.light_energy=0.35; world.environment.background_energy_multiplier=0.95
		elif lighting=="backlight": sun.rotate_y(PI)
	await create_timer(seconds).timeout
	await RenderingServer.frame_post_draw
	var screenshot := root.get_texture().get_image(); screenshot.save_png(output)
	var report := {"mode":mode,"lighting":lighting,"view":view,"sdfgi":gi,"resolution":[screenshot.get_width(),screenshot.get_height()],"fov":camera.fov,"settle_seconds":seconds,"profile":profile.title,"gpu":RenderingServer.get_video_adapter_name(),"engine":Engine.get_version_info()}
	if mode=="native": report.merge({"terrain":scene.terrain.statistics(),"ecology":scene.ecology.statistics()})
	elif mode=="study": report.merge({"instances":scene.content.get_meta("instances"),"terrain_triangles":scene.content.get_meta("terrain_triangles"),"scatter_triangles":scene.content.get_meta("scatter_triangles"),"source_sha256":scene.content.get_meta("source_sha256")})
	var file := FileAccess.open(output+".json",FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	print("OPD_VISUAL_CAPTURE ",JSON.stringify(report))
	scene.queue_free()
	for frame in 4: await process_frame
	await RenderingServer.frame_post_draw
	quit()
