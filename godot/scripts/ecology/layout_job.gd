# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
const Cell=preload("res://scripts/ecology/cell_job.gd")
var cells: Array=[]
var camera: PackedFloat64Array
var tree_reach: float
var ground_reach: float
var tree_full: float=9.0
var tree_medium: float=65.0
var cover_full: float=12.0
var cover_medium: float=26.0
var groups: Dictionary={}
var instance_count: int=0
var triangle_budget: int=5000000
var instance_budget: int=30000
var triangles: Dictionary={}
var expanded_triangles: int=0
var downgraded: int=0
var budget_culled: int=0

func run() -> void:
	groups.clear(); instance_count=0; expanded_triangles=0; downgraded=0; budget_culled=0
	var candidates := []
	for cell in cells:
		var records: PackedFloat64Array=cell.records
		var centre: PackedFloat64Array=cell.centre
		for i in records.size()/16:
			var j := i*16
			var dx: float=records[j]-camera[0]; var dy: float=records[j+1]-camera[1]; var dz: float=records[j+2]-camera[2]
			var distance := sqrt(dx*dx+dy*dy+dz*dz)
			var kind := int(records[j+12]); var ground: bool=cell.ground
			if distance>(ground_reach if ground else tree_reach): continue
			var first := cover_full if ground else tree_full
			var second := maxf(first+1.0,cover_medium if ground else tree_medium)
			# Persistent variation spreads transitions across the landscape.
			var factor: float=0.9+0.2*records[j+14]
			var lod := 0 if distance<first*factor else (1 if distance<second*factor else 2)
			candidates.append({"cell":cell,"j":j,"kind":kind,"lod":lod,"distance":distance,"id":cell.ids[i]})
	candidates.sort_custom(func(a: Dictionary,b: Dictionary): return a.distance<b.distance if a.distance!=b.distance else str(a.id)<str(b.id))
	budget_culled=maxi(0,candidates.size()-instance_budget)
	if candidates.size()>instance_budget: candidates.resize(instance_budget)
	var base := 0
	for candidate in candidates: base+=_cost(candidate.kind,2)
	while base>triangle_budget and not candidates.is_empty():
		base-=_cost(candidates.pop_back().kind,2); budget_culled+=1
	var remaining := triangle_budget-base
	for candidate in candidates:
		var kind: int=candidate.kind; var lod: int=candidate.lod
		while lod<2 and _cost(kind,lod)-_cost(kind,2)>remaining: lod+=1
		remaining-=_cost(kind,lod)-_cost(kind,2); expanded_triangles+=_cost(kind,lod)
		if lod!=candidate.lod: downgraded+=1
		var cell: Dictionary=candidate.cell; var j: int=candidate.j
		var centre: PackedFloat64Array=cell.centre; var records: PackedFloat64Array=cell.records
		var key: String=cell.tile.key+"/"+str(kind)+"/"+str(lod)
		if not groups.has(key): groups[key]={"key":key,"prototype":Cell.KINDS[kind]+"_"+str(lod),"centre":centre,"buffer":[],"count":0,"lod":lod,"ground":cell.ground}
		# Native MultiMesh's bulk buffer is three rows of basis + translation.
		groups[key].buffer.append_array([records[j+3],records[j+6],records[j+9],records[j]-centre[0],records[j+4],records[j+7],records[j+10],records[j+1]-centre[1],records[j+5],records[j+8],records[j+11],records[j+2]-centre[2]])
		groups[key].count+=1; instance_count+=1
	for group in groups.values(): group.buffer=PackedFloat32Array(group.buffer)

func _cost(kind: int,lod: int) -> int:
	return int(triangles.get(Cell.KINDS[kind]+"_"+str(lod),1))
