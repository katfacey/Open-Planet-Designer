# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree

func _initialize() -> void:
	var packed: PackedScene=load("res://assets/generated/models/grass_0.glb")
	var model:=packed.instantiate()
	for child in model.get_children():
		if child is MeshInstance3D:
			var material: StandardMaterial3D=child.mesh.surface_get_material(0)
			var colors: PackedColorArray=child.mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
			var active: StandardMaterial3D=child.get_active_material(0)
			print("GRASS_MATERIAL ",JSON.stringify({"vertex_color_enabled":material.vertex_color_use_as_albedo,
				"albedo":str(material.albedo_color),"roughness":material.roughness,"specular":material.metallic_specular,
				"active_vertex_color_enabled":active.vertex_color_use_as_albedo,
				"vertices_with_color":colors.size(),"first_color":str(colors[0])}))
	model.free(); quit()
