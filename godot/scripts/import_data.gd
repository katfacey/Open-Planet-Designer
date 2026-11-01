# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted

const ROOT := "res://assets/generated/"

static func read_terrain(path: String) -> Array:
	var bytes := FileAccess.get_file_as_bytes(ROOT + path)
	if bytes.size() < 8:
		return []
	var n := int(bytes.decode_u32(0))
	var index_count := int(bytes.decode_u32(4))
	if bytes.size() != 8 + n * 48 + index_count * 4:
		push_error("Invalid terrain buffer: " + path)
		return []
	var p := bytes.slice(8, 8 + n * 12).to_float32_array()
	var normal := bytes.slice(8 + n * 12, 8 + n * 24).to_float32_array()
	var color := bytes.slice(8 + n * 24, 8 + n * 40).to_float32_array()
	var uv := bytes.slice(8 + n * 40, 8 + n * 48).to_float32_array()
	var positions := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var uvs := PackedVector2Array()
	positions.resize(n); normals.resize(n); colors.resize(n); uvs.resize(n)
	for i in n:
		positions[i] = Vector3(p[i * 3], p[i * 3 + 1], p[i * 3 + 2])
		normals[i] = Vector3(normal[i * 3], normal[i * 3 + 1], normal[i * 3 + 2])
		colors[i] = Color(color[i * 4], color[i * 4 + 1], color[i * 4 + 2], color[i * 4 + 3])
		uvs[i] = Vector2(uv[i * 2], uv[i * 2 + 1])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = positions
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = bytes.slice(8 + n * 48).to_int32_array()
	return arrays

static func read_instances(path: String) -> Dictionary:
	var bytes := FileAccess.get_file_as_bytes(ROOT + path)
	if bytes.size() < 4:
		return {}
	var count := int(bytes.decode_u32(0))
	if bytes.size() != 4 + count * 52:
		push_error("Invalid instance buffer: " + path)
		return {}
	return {"count": count, "transforms": bytes.slice(4, 4 + count * 48).to_float32_array(),
		"ids": bytes.slice(4 + count * 48).to_int32_array()}

static func instance_transform(data: PackedFloat32Array, index: int) -> Transform3D:
	var i := index * 12
	return Transform3D(Basis(Vector3(data[i], data[i+1], data[i+2]),
		Vector3(data[i+3], data[i+4], data[i+5]), Vector3(data[i+6], data[i+7], data[i+8])),
		Vector3(data[i+9], data[i+10], data[i+11]))

static func vec(array: Array) -> Vector3:
	return Vector3(array[0], array[1], array[2])

static func basis(array: Array) -> Basis:
	return Basis(Vector3(array[0],array[1],array[2]),Vector3(array[3],array[4],array[5]),Vector3(array[6],array[7],array[8]))
