# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
## Analytic swept camera sphere against nearby canonical trunks and rocks.
## Walking, overhang collision and a full physics controller remain separate work.
static func sweep(start: PackedFloat64Array,target: PackedFloat64Array,cells: Array,radius: float=0.25) -> PackedFloat64Array:
	var motion := Location.local(target,start)
	if motion.length_squared()<0.00000001: return target
	var fraction := 1.0
	for cell in cells:
		if cell.ground or Location.distance(start,cell.centre)>motion.length()+200.0: continue
		var records: PackedFloat64Array=cell.records
		for i in records.size()/16:
			var j := i*16; var kind := int(records[j+12])
			var height: float=records[j+13]
			var delta := Vector3(start[0]-records[j],start[1]-records[j+1],start[2]-records[j+2])
			if delta.length_squared()>pow(motion.length()+height+1.0,2.0): continue
			var up := Vector3(records[j+6],records[j+7],records[j+8]).normalized()
			var velocity := motion; var r := radius+maxf(0.12,height*0.017)
			var h := delta.dot(up); var vh := motion.dot(up)
			if kind==6:
				delta-=up*height*0.25; r=radius+height*0.55
			else:
				delta-=up*h; velocity-=up*vh
			var a := velocity.length_squared()
			if a<0.0000001: continue
			var b := 2.0*delta.dot(velocity); var c := delta.length_squared()-r*r
			var discriminant := b*b-4.0*a*c
			if discriminant<0.0 or c<0.0: continue
			var t := (-b-sqrt(discriminant))/(2.0*a)
			if t>=0.0 and t<fraction and (kind==6 or (h+vh*t>=0.0 and h+vh*t<height*0.7)):
				fraction=maxf(0.0,t-0.01/motion.length())
	return PackedFloat64Array([lerpf(start[0],target[0],fraction),lerpf(start[1],target[1],fraction),lerpf(start[2],target[2],fraction)])
