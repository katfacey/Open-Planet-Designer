# SPDX-License-Identifier: GPL-3.0-or-later
extends "res://scripts/streaming/tile_job.gd"
const Location=preload("res://scripts/world/planet_location.gd")
const FieldNoise=preload("res://scripts/terrain/canonical_noise.gd")
const KINDS=["TREE","TREE_B","TREE_C","SAPLING","FIR","DEAD","ROCK","GRASS","FERN","WILDGRASS"]
var ground: bool=false

func generate() -> Dictionary:
	var records := PackedFloat64Array(); var ids := PackedStringArray()
	var side := 48 if ground else 8
	var centre: PackedFloat64Array=provider.position(Location.tile_direction(tile,0.5,0.5))
	for y in side:
		for x in side:
			var cell_x: int=tile.x*side+x; var cell_y: int=tile.y*side+y
			var seed: int=provider.seed+tile.face*191+(2341 if ground else 0)
			var random := FieldNoise.hash3(cell_x,cell_y,3,seed)*0.5+0.5
			var u: float=(x+0.15+0.7*(FieldNoise.hash3(cell_x,cell_y,7,seed)*0.5+0.5))/side
			var v: float=(y+0.15+0.7*(FieldNoise.hash3(cell_x,cell_y,11,seed)*0.5+0.5))/side
			var d := Location.tile_direction(tile,u,v)
			var field: PackedFloat64Array=provider.sample(d)
			var slope: float=field[1]*d[0]+field[2]*d[1]+field[3]*d[2]
			if field[0]<provider.sea_level+0.5 or slope<0.65: continue
			if random>(0.72 if ground else 0.06+field[4]*0.62): continue
			var kind := 7; var height := 0.3+0.3*random
			if ground:
				kind=8 if field[4]>0.65 and random<0.12 else (9 if random>0.42 else 7)
				height=0.25+0.35*(FieldNoise.hash3(cell_x,cell_y,17,seed)*0.5+0.5)
			else:
				var age := FieldNoise.hash3(cell_x,cell_y,19,seed)*0.5+0.5
				kind=int(random*3.0)%3
				height=12.0+10.0*age
				if age<0.18: kind=3; height=2.0+5.0*random
				elif age<0.3: kind=4; height=4.0+7.0*random
				elif age>0.95: kind=5
				if field[4]<0.22 and random<0.04: kind=6; height=0.4+random*8.0
			var up := PackedFloat64Array([field[1],field[2],field[3]]) if ground or kind==6 else d
			var basis := Location.frame(up)*Basis(Vector3.UP,random*TAU)
			basis=basis.scaled(Vector3.ONE*height)
			var p := Location.point(d,provider.radius_m+field[0])
			records.append_array(PackedFloat64Array([p[0],p[1],p[2],basis.x.x,basis.x.y,basis.x.z,basis.y.x,basis.y.y,basis.y.z,basis.z.x,basis.z.y,basis.z.z,float(kind),height,random,field[4]]))
			ids.append("%s/%s/%d/%d" % [provider.identity_namespace,tile.key,x,y])
	return {"tile":tile,"centre":centre,"records":records,"ids":ids,"ground":ground}
