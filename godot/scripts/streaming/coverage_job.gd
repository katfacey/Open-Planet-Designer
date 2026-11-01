# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Selector=preload("res://scripts/terrain/tile_selector.gd")
var cover: Dictionary={}
var masks: Dictionary={}
var generation: int=0
var valid: bool=false

func run() -> void:
	valid=false; masks.clear()
	var areas := PackedFloat64Array([0,0,0,0,0,0])
	for tile in cover.values(): areas[tile.face]+=pow(0.25,float(tile.level))
	for area in areas:
		if absf(area-1.0)>1e-10: return
	# A balanced desired selection does not guarantee balanced partial residency.
	# Keep the previous complete cover until every new boundary is stitchable.
	for tile in cover.values():
		for edge in 4:
			var other := Selector.neighbour(tile,edge,cover)
			if other.is_empty() or absi(int(tile.level)-int(other.level))>1: return
	for key in cover: masks[key]=Selector.stitch_mask(cover[key],cover)
	valid=true
