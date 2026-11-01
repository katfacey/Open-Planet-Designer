# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
## Offline conversion of the preserved Blender forest into a portable local study.
const Data=preload("res://scripts/import_data.gd")
func _initialize() -> void:
	root.position=Vector2i(-5000,-5000)
	if DisplayServer.get_name()=="headless":
		push_error("Bake the study with Vulkan, without --headless: Dummy rendering cannot serialize MultiMesh GPU buffers."); quit(1); return
	call_deferred("build")

func find_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D: return node
	for child in node.get_children():
		var found := find_mesh(child)
		if found!=null: return found
	return null

func own(node: Node,parent: Node) -> void:
	node.owner=parent
	for child in node.get_children(): own(child,parent)

func build() -> void:
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/generated/manifest.json"))
	var data: Dictionary=manifest.sites.Forest
	var catalogue: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/catalog/catalog.json"))
	var look: Resource=load("res://earth_woodland.tres")
	var study := Node3D.new(); study.name="PreservedForestGeometry"
	var ground: ShaderMaterial=look.ground_material(true)
	var triangles := 0
	for chunk in data.terrain:
		var mesh := ArrayMesh.new(); mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,Data.read_terrain(chunk.file))
		var node := MeshInstance3D.new(); node.name="Terrain"; node.mesh=mesh; node.material_override=ground
		node.position=Data.vec(chunk.center); study.add_child(node)
		triangles+=int(chunk.triangles)
		if node.position.length()>2000.0:
			node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			node.gi_mode=GeometryInstance3D.GI_MODE_DISABLED
		else:
			node.gi_mode=GeometryInstance3D.GI_MODE_STATIC
			if int(chunk.triangles)>100: node.create_trimesh_collision()
	var instances := 0; var scatter_triangles := 0
	for record in data.instances:
		var source_scene: Node=load("res://assets/catalog/"+catalogue.prototypes[record.prototype].file).instantiate()
		var source := find_mesh(source_scene)
		var mesh: ArrayMesh=source.mesh.duplicate()
		for surface in mesh.get_surface_count(): mesh.surface_set_material(surface,look.prepare_material(source.get_active_material(surface),record.kind))
		var input: Dictionary=Data.read_instances(record.file)
		var multi := MultiMesh.new(); multi.transform_format=MultiMesh.TRANSFORM_3D; multi.mesh=mesh; multi.instance_count=input.count
		for i in int(input.count): multi.set_instance_transform(i,Data.instance_transform(input.transforms,i))
		var node := MultiMeshInstance3D.new(); node.name=str(record.prototype); node.multimesh=multi; node.lod_bias=8.0
		node.gi_mode=GeometryInstance3D.GI_MODE_STATIC if int(record.level)<2 else GeometryInstance3D.GI_MODE_DYNAMIC
		if int(record.level)==2: node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		study.add_child(node)
		instances+=int(input.count); scatter_triangles+=int(input.count)*int(catalogue.prototypes[record.prototype].triangles)
		source_scene.free()
	study.set_meta("camera_basis",data.camera_basis); study.set_meta("camera_fov",data.camera_fov_deg)
	study.set_meta("sun_basis",data.sun_basis)
	study.set_meta("source_sha256",manifest.source_sha256)
	study.set_meta("instances",instances); study.set_meta("terrain_triangles",triangles); study.set_meta("scatter_triangles",scatter_triangles)
	await process_frame
	await RenderingServer.frame_post_draw
	for child in study.get_children(): own(child,study)
	var packed := PackedScene.new(); var error := packed.pack(study)
	if error==OK: error=ResourceSaver.save(packed,"res://assets/appearance/forest_study.scn",ResourceSaver.FLAG_COMPRESS)
	study.free()
	if error!=OK: push_error("Forest study save failed: "+str(error)); quit(1); return
	var report := {"source_sha256":manifest.source_sha256,"instances":instances,"terrain_triangles":triangles,"scatter_triangles":scatter_triangles,"scope":"Fixed original camera populations and terrain; local visual benchmark, not native streaming"}
	var file := FileAccess.open("res://assets/appearance/study.json",FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	print("OPD_STUDY_BUILT ",JSON.stringify(report)); quit()
