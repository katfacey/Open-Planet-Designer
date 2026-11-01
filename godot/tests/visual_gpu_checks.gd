# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
var output: String="user://visual-gpu-checks.json"
func _initialize() -> void:
	root.position=Vector2i(-5000,-5000)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): output=arg.trim_prefix("--report=")
	call_deferred("check")

func check() -> void:
	var scene: Node3D=load("res://woodland_study.tscn").instantiate(); root.add_child(scene)
	while not scene.ready_for_capture: await process_frame
	scene.set_physics_process(false); scene.set_process_input(false)
	await RenderingServer.frame_post_draw
	var count := 0; var buffers := true; var proxies := true
	for node in scene.content.get_children():
		if node is MultiMeshInstance3D:
			count+=node.multimesh.instance_count
			buffers=buffers and node.multimesh.buffer.size()==node.multimesh.instance_count*12
			if node.name.ends_with("_2"): proxies=proxies and node.gi_mode!=GeometryInstance3D.GI_MODE_STATIC
	var fern: MultiMeshInstance3D=scene.content.get_node("FERN_0")
	var transform := fern.multimesh.get_instance_transform(0)
	var origin_ok := transform.origin.distance_to(Vector3(1.68919098377,-1.81856882572,-2.16903662682))<0.00001
	await physics_frame; await process_frame
	var ray := PhysicsRayQueryParameters3D.create(Vector3(0,5,0),Vector3(0,-20,0))
	var hit: Dictionary=scene.get_world_3d().direct_space_state.intersect_ray(ray)
	var checks := {"all_original_instances_present":count==59212,"gpu_instance_buffers_are_populated":buffers,
		"original_fern_transform_preserved":origin_ok,"impostors_excluded_from_static_gi":proxies,
		"terrain_has_physical_collision":not hit.is_empty(),"projection_ratio_is_representable":scene.camera.far/scene.camera.near<=100001.0,
		"matched_blender_camera_fov":absf(scene.camera.fov-35.1153934441)<0.0001}
	var passed := true
	for value in checks.values(): passed=passed and bool(value)
	var report := {"passed":passed,"checks":checks,"instances":count,"engine":Engine.get_version_info()}
	var file := FileAccess.open(output,FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	print("OPD_VISUAL_GPU_CHECKS ",JSON.stringify(report)); scene.queue_free(); await process_frame; quit(0 if passed else 1)
