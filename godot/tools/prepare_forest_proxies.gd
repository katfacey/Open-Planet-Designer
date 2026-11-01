# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
## Offline simplification keeps real 3D branching in the medium/far forest.
const KINDS=["TREE","TREE_B","TREE_C","SAPLING","FIR","DEAD","ROCK"]
func _initialize() -> void:
	call_deferred("prepare")

func find_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D: return node
	for child in node.get_children():
		var found := find_mesh(child)
		if found!=null: return found
	return null

func prepare() -> void:
	var folder := "res://assets/appearance/proxies"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(folder))
	var records := {}
	for kind in KINDS:
		var path: String="res://assets/catalog/models/"+str(kind).to_lower()+"_1.gltf"
		var scene: Node=load(path).instantiate(); var source := find_mesh(scene)
		var importer := ImporterMesh.new()
		var original := 0
		for surface in source.mesh.get_surface_count():
			var arrays: Array=source.mesh.surface_get_arrays(surface)
			original+=arrays[Mesh.ARRAY_INDEX].size()/3
			importer.add_surface(Mesh.PRIMITIVE_TRIANGLES,arrays,[],{},source.get_active_material(surface))
		importer.generate_lods(60.0,25.0,[])
		var mesh := ArrayMesh.new(); var triangles := 0
		var target := 1800.0 if str(kind).begins_with("TREE") else 1500.0
		for surface in importer.get_surface_count():
			# Generic simplification destroys alpha-leaf coverage. Keep the prepared
			# directional crowns, and simplify only real wood/rock geometry.
			var material: Material=source.get_active_material(surface)
			if material is StandardMaterial3D and material.transparency!=BaseMaterial3D.TRANSPARENCY_DISABLED: continue
			var arrays: Array=importer.get_surface_arrays(surface)
			var indices: PackedInt32Array=arrays[Mesh.ARRAY_INDEX]
			var wanted := maxi(12,int(float(indices.size())/3.0*target/maxi(1,original)))
			var best := indices
			for level in importer.get_surface_lod_count(surface):
				var candidate: PackedInt32Array=importer.get_surface_lod_indices(surface,level)
				if absf(candidate.size()/3.0-wanted)<absf(best.size()/3.0-wanted): best=candidate
			arrays[Mesh.ARRAY_INDEX]=best; triangles+=best.size()/3
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			mesh.surface_set_material(mesh.get_surface_count()-1,source.get_active_material(surface).duplicate())
		var crown_scene: Node=load("res://assets/catalog/models/"+str(kind).to_lower()+"_2.gltf").instantiate()
		var crown := find_mesh(crown_scene)
		for surface in crown.mesh.get_surface_count():
			var material: Material=crown.get_active_material(surface)
			if not material is StandardMaterial3D or material.transparency==BaseMaterial3D.TRANSPARENCY_DISABLED: continue
			var arrays: Array=crown.mesh.surface_get_arrays(surface)
			triangles+=arrays[Mesh.ARRAY_INDEX].size()/3
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			mesh.surface_set_material(mesh.get_surface_count()-1,material.duplicate())
		crown_scene.free()
		var destination: String=folder+"/"+str(kind).to_lower()+".res"
		var error := ResourceSaver.save(mesh,destination,ResourceSaver.FLAG_COMPRESS)
		if error!=OK: push_error("Proxy save failed: "+str(kind)); quit(1); return
		records[kind]={"file":destination,"source":path,"source_triangles":original,"triangles":triangles,"method":"Simplified opaque 3D wood/rock plus retained directional alpha crowns; original UVs/normals/material slots"}
		scene.free()
		print("FOREST_PROXY ",kind," ",original," -> ",triangles)
	var file := FileAccess.open("res://assets/appearance/proxies.json",FileAccess.WRITE)
	file.store_string(JSON.stringify({"schema":1,"license":"CC0 source assets; see CREDITS.json and project source credits","proxies":records},"\t")); file.close()
	quit()
