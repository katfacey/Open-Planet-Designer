# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
const SEGMENTS:=32
const SIDE:=SEGMENTS+1
const VERTICES:=SIDE*SIDE

static func generate(provider: RefCounted,tile: Dictionary) -> Dictionary:
	var started := Time.get_ticks_usec()
	var centre := provider.position(Location.tile_direction(tile,0.5,0.5)) as PackedFloat64Array
	var positions := PackedVector3Array(); positions.resize(VERTICES)
	var normals := PackedVector3Array(); normals.resize(VERTICES)
	var colors := PackedColorArray(); colors.resize(VERTICES)
	var uvs := PackedVector2Array(); uvs.resize(VERTICES)
	var custom := PackedFloat32Array(); custom.resize(VERTICES*4)
	var min_height := INF; var max_height := -INF
	# 234 m is an exact repeat multiple for the 2 / 1.3 / 1.8 / 3 m scans.
	# Wrapping at an arbitrary UV period introduces seams in rescaled layers.
	var phase_x: float=fposmod(centre[0],234.0)/2.0
	var phase_z: float=fposmod(centre[2],234.0)/2.0
	for y in SIDE:
		for x in SIDE:
			var i := y*SIDE+x
			var d := Location.tile_direction(tile,float(x)/SEGMENTS,float(y)/SEGMENTS)
			var field: PackedFloat64Array=provider.sample(d)
			var p := Location.point(d,provider.radius_m+field[0])
			positions[i]=Location.local(p,centre)
			normals[i]=Vector3(field[1],field[2],field[3])
			colors[i]=Color(field[6],field[4],field[8],field[7])
			uvs[i]=Vector2(phase_x+positions[i].x/2.0,phase_z+positions[i].z/2.0)
			custom[i*4+3]=field[1]*d[0]+field[2]*d[1]+field[3]*d[2]
			min_height=minf(min_height,field[0]); max_height=maxf(max_height,field[0])
	# Parent-triangle interpolation, stored as local deltas. Fixed border positions
	# let independent tiles morph without opening their shared boundaries.
	for y in range(1,SEGMENTS):
		for x in range(1,SEGMENTS):
			var i := y*SIDE+x
			var x0 := (x>>1)*2; var y0 := (y>>1)*2
			var tx := float(x-x0)/2.0; var ty := float(y-y0)/2.0
			var a: Vector3=positions[y0*SIDE+x0]; var b: Vector3=positions[y0*SIDE+x0+2]
			var c: Vector3=positions[(y0+2)*SIDE+x0]; var d: Vector3=positions[(y0+2)*SIDE+x0+2]
			var p: Vector3=a+(b-a)*tx+(c-a)*ty if tx+ty<=1.0 else d+(b-d)*(1.0-ty)+(c-d)*(1.0-tx)
			var delta: Vector3=p-positions[i]
			custom[i*4]=delta.x; custom[i*4+1]=delta.y; custom[i*4+2]=delta.z
	return {"tile":tile,"centre":centre,"positions":positions,"normals":normals,"colors":colors,"uvs":uvs,"custom":custom,
		"min_height":min_height,"max_height":max_height,"generation_ms":(Time.get_ticks_usec()-started)/1000.0}

static func indices(mask: int) -> PackedInt32Array:
	var result := PackedInt32Array()
	for y in SEGMENTS:
		for x in SEGMENTS:
			var a := edge_index(x,y,mask); var b := edge_index(x+1,y,mask)
			var c := edge_index(x,y+1,mask); var d := edge_index(x+1,y+1,mask)
			if a!=c and c!=b and a!=b: result.append_array(PackedInt32Array([a,c,b]))
			if b!=c and c!=d and b!=d: result.append_array(PackedInt32Array([b,c,d]))
	return result

static func edge_index(x: int,y: int,mask: int) -> int:
	if (x==0 and (mask&1)!=0) or (x==SEGMENTS and (mask&2)!=0): y-=y&1
	if (y==0 and (mask&4)!=0) or (y==SEGMENTS and (mask&8)!=0): x-=x&1
	return y*SIDE+x

static func arrays(data: Dictionary,mask: int) -> Array:
	var result := []; result.resize(Mesh.ARRAY_MAX)
	result[Mesh.ARRAY_VERTEX]=data.positions; result[Mesh.ARRAY_NORMAL]=data.normals
	result[Mesh.ARRAY_COLOR]=data.colors; result[Mesh.ARRAY_TEX_UV]=data.uvs
	result[Mesh.ARRAY_CUSTOM0]=data.custom; result[Mesh.ARRAY_INDEX]=indices(mask)
	return result
