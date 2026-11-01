# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
var leaves: Dictionary={}
var unmet_error_pixels: float=0.0
var result: Dictionary={}
var elapsed_ms: float=0.0
var contact_radius: float=50.0
var trunk_radius: float=70.0

func run(provider: RefCounted,definition: Resource,camera: PackedFloat64Array,focal: float) -> void:
	var started := Time.get_ticks_usec()
	result=select(provider,definition,camera,focal)
	elapsed_ms=(Time.get_ticks_usec()-started)/1000.0

func select(provider: RefCounted,definition: Resource,camera: PackedFloat64Array,focal: float) -> Dictionary:
	contact_radius=minf(100.0,definition.ground_reach_m+5.0)
	trunk_radius=minf(100.0,definition.tree_medium_detail_m+5.0)
	leaves.clear()
	for face in 6:
		var root := Location.tile(face,0,0,0); leaves[root.key]=root
	var budget := mini(definition.leaf_budget,maxi(6,definition.resident_tile_limit/3))
	var blocked := {}
	while leaves.size()+3<=budget:
		var best := {}; var largest: float=definition.terrain_pixels
		for tile in leaves.values():
			if tile.level>=definition.max_depth or blocked.has(tile.key): continue
			if not tile.has("score"): tile.score=_score(provider,tile,camera,focal)
			if float(tile.score)>largest: best=tile; largest=tile.score
		if best.is_empty(): break
		# Include every required balancing split BEFORE spending the leaf budget.
		var closure := {}; var queue := [best]
		while not queue.is_empty():
			var tile: Dictionary=queue.pop_back()
			if closure.has(tile.key): continue
			closure[tile.key]=tile
			for edge in 4:
				var other := neighbour(tile,edge,leaves)
				if not other.is_empty() and other.level<tile.level and not closure.has(other.key): queue.append(other)
		if leaves.size()+closure.size()*3>budget: blocked[best.key]=true; continue
		for tile in closure.values(): _split(tile)
	var selected := leaves.duplicate(true)
	unmet_error_pixels=0.0
	for tile in selected.values(): unmet_error_pixels=maxf(unmet_error_pixels,_score(provider,tile,camera,focal,false))
	return selected

func _split(tile: Dictionary) -> void:
	leaves.erase(tile.key)
	for child in Location.children(tile): leaves[child.key]=child

func _score(provider: RefCounted,tile: Dictionary,camera: PackedFloat64Array,focal: float,prioritize_contacts: bool=true) -> float:
	var d := Location.tile_direction(tile,0.5,0.5)
	var span: float=provider.radius_m*2.0/float(1<<int(tile.level))
	# Do not spend fine detail behind the planet. Parent geometry remains present.
	var altitude: float=maxf(Location.radius(camera)-provider.radius_m,0.0)
	var angle: float=acos(clampf((camera[0]*d[0]+camera[1]*d[1]+camera[2]*d[2])/Location.radius(camera),-1.0,1.0))
	if angle>acos(clampf(provider.radius_m/(provider.radius_m+altitude+8000.0),0.0,1.0))+span/provider.radius_m*1.5: return 0.0
	var projected := Location.project(tile.face,camera)
	var scale := float(1<<int(tile.level))
	var u := clampf(projected[0],-1.0+2.0*tile.x/scale,-1.0+2.0*(tile.x+1)/scale)
	var v := clampf(projected[1],-1.0+2.0*tile.y/scale,-1.0+2.0*(tile.y+1)/scale)
	var nearest: PackedFloat64Array=provider.position(Location.direction(tile.face,u,v))
	var distance: float=maxf(1.0,Location.distance(camera,nearest))
	var pixels: float=provider.error_bound(span/32.0,d)*focal/distance
	if prioritize_contacts:
		if (distance<contact_radius and span/32.0>0.45) or (distance<trunk_radius and span/32.0>1.0):
			return maxf(pixels,100000000.0/(distance+1.0))
	return pixels

static func neighbour(tile: Dictionary,edge: int,collection: Dictionary) -> Dictionary:
	var step := 1.0/float(1<<int(tile.level))
	var x := 0.5; var y := 0.5
	if edge==0: x=-0.00001
	elif edge==1: x=1.00001
	elif edge==2: y=-0.00001
	else: y=1.00001
	var d := Location.tile_direction(tile,x,y)
	var address := Location.address(d)
	for level in range(25):
		var size := 1<<level
		var ix := clampi(int(floor((float(address.u)+1.0)*0.5*size)),0,size-1)
		var iy := clampi(int(floor((float(address.v)+1.0)*0.5*size)),0,size-1)
		var key := Location.tile_key(address.face,level,ix,iy)
		if collection.has(key): return collection[key]
	return {}

static func stitch_mask(tile: Dictionary,collection: Dictionary) -> int:
	var mask := 0
	for edge in 4:
		var other := neighbour(tile,edge,collection)
		if not other.is_empty() and other.level<tile.level: mask|=1<<edge
	return mask
