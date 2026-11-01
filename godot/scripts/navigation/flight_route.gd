# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
var name: String="Woodland boundary and return"
var duration: float=60.0
var anchors: Array=[]

func configure(route_name: String="woodland",seconds: float=60.0) -> void:
	duration=seconds
	if route_name=="orbit":
		name="Orbital descent and reverse exit"
		anchors=[[0.0,2,0.08,0.11,2500000.0,-80.0],[0.25,2,0.08,0.11,5000.0,-55.0],[0.48,2,0.0801,0.1101,20.0,-12.0],[0.55,2,0.0801,0.1101,2.2,-5.0],[0.75,2,0.08,0.11,5000.0,20.0],[1.0,2,0.08,0.11,2500000.0,-80.0]]
	elif route_name=="seam":
		name="Cube-face seam and return"
		anchors=[[0.0,2,0.9998,0.04,300.0,-30.0],[0.5,2,1.0002,0.04,150.0,-20.0],[1.0,2,0.9998,0.04,300.0,-30.0]]
	elif route_name=="forest":
		name="Dense woodland and meadow return"
		anchors=[[0.0,2,0.0798,0.11015,2.2,-5.0],[0.2,2,0.0798,0.11015,40.0,-25.0],[0.5,2,0.0801,0.1102,20.0,-10.0],[0.8,2,0.0798,0.11015,50.0,-25.0],[1.0,2,0.0798,0.11015,2.2,-5.0]]
	else:
		anchors=[[0.0,2,0.08,0.11,2.2,-5.0],[0.1,2,0.08,0.11,35.0,-15.0],[0.45,2,0.0805,0.11015,70.0,-25.0],[0.55,2,0.0805,0.11015,2.2,-5.0],[0.9,2,0.08,0.11,35.0,-20.0],[1.0,2,0.08,0.11,2.2,-5.0]]

func position_at(seconds: float,provider: RefCounted) -> Dictionary:
	var progress := clampf(seconds/duration,0.0,1.0)
	var a: Array=anchors[0]; var b: Array=anchors[-1]
	for i in range(anchors.size()-1):
		if progress>=float(anchors[i][0]) and progress<=float(anchors[i+1][0]): a=anchors[i]; b=anchors[i+1]; break
	var t := clampf((progress-float(a[0]))/maxf(0.00001,float(b[0])-float(a[0])),0.0,1.0)
	t=t*t*(3.0-2.0*t)
	var d := Location.direction(int(a[1]),lerpf(a[2],b[2],t),lerpf(a[3],b[3],t))
	var height: float=provider.height(d)+lerpf(a[4],b[4],t)
	return {"position":Location.point(d,provider.radius_m+height),"pitch":deg_to_rad(lerpf(a[5],b[5],t)),"direction":d}
