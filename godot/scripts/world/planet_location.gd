# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
## Absolute positions stay scalar float64 until AFTER origin subtraction.

static func direction(face: int, u: float, v: float) -> PackedFloat64Array:
	var a := PackedFloat64Array()
	match face:
		0: a=PackedFloat64Array([1.0,u,v])
		1: a=PackedFloat64Array([-1.0,-u,v])
		2: a=PackedFloat64Array([-u,1.0,v])
		3: a=PackedFloat64Array([u,-1.0,v])
		4: a=PackedFloat64Array([u,v,1.0])
		_: a=PackedFloat64Array([u,-v,-1.0])
	var length := sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2])
	return PackedFloat64Array([a[0]/length,a[1]/length,a[2]/length])

static func address(p: PackedFloat64Array) -> Dictionary:
	var x: float=p[0]; var y: float=p[1]; var z: float=p[2]
	var m: float=max(abs(x),max(abs(y),abs(z)))
	if m==0.0: return {"face":2,"u":0.0,"v":0.0}
	if abs(x)>=abs(y) and abs(x)>=abs(z):
		return {"face":0 if x>=0.0 else 1,"u":y/x,"v":z/abs(x)}
	if abs(y)>=abs(z):
		return {"face":2 if y>=0.0 else 3,"u":-x/y,"v":z/abs(y)}
	return {"face":4 if z>=0.0 else 5,"u":x/abs(z),"v":y/z}

static func point(d: PackedFloat64Array, radius: float) -> PackedFloat64Array:
	return PackedFloat64Array([d[0]*radius,d[1]*radius,d[2]*radius])

static func local(p: PackedFloat64Array, origin: PackedFloat64Array) -> Vector3:
	return Vector3(p[0]-origin[0],p[1]-origin[1],p[2]-origin[2])

static func distance(a: PackedFloat64Array,b: PackedFloat64Array) -> float:
	var x: float=a[0]-b[0]; var y: float=a[1]-b[1]; var z: float=a[2]-b[2]
	return sqrt(x*x+y*y+z*z)

static func radius(p: PackedFloat64Array) -> float:
	return sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2])

static func normalized(p: PackedFloat64Array) -> PackedFloat64Array:
	var r := radius(p)
	return point(p,1.0/max(r,0.000001))

static func frame(d: PackedFloat64Array) -> Basis:
	var up := Vector3(d[0],d[1],d[2]).normalized()
	# Select a well-conditioned axis, including either pole.
	var reference := Vector3.FORWARD if abs(up.z)<0.8 else Vector3.RIGHT
	var east := reference.cross(up).normalized()
	return Basis(east,up,east.cross(up).normalized())

static func tile_key(face: int,level: int,x: int,y: int) -> String:
	return "%d/%d/%d/%d" % [face,level,x,y]

static func project(face: int,p: PackedFloat64Array) -> PackedFloat64Array:
	var x: float=p[0]; var y: float=p[1]; var z: float=p[2]
	match face:
		0: return PackedFloat64Array([y/maxf(x,0.000001),z/maxf(x,0.000001)])
		1: return PackedFloat64Array([-y/maxf(-x,0.000001),z/maxf(-x,0.000001)])
		2: return PackedFloat64Array([-x/maxf(y,0.000001),z/maxf(y,0.000001)])
		3: return PackedFloat64Array([x/maxf(-y,0.000001),z/maxf(-y,0.000001)])
		4: return PackedFloat64Array([x/maxf(z,0.000001),y/maxf(z,0.000001)])
		_: return PackedFloat64Array([x/maxf(-z,0.000001),-y/maxf(-z,0.000001)])

static func tile(face: int,level: int,x: int,y: int) -> Dictionary:
	return {"face":face,"level":level,"x":x,"y":y,"key":tile_key(face,level,x,y)}

static func children(t: Dictionary) -> Array:
	var result := []
	for y in 2:
		for x in 2: result.append(tile(t.face,t.level+1,t.x*2+x,t.y*2+y))
	return result

static func parent_key(t: Dictionary) -> String:
	return tile_key(t.face,t.level-1,t.x>>1,t.y>>1)

static func uv(t: Dictionary,x: float,y: float) -> Vector2:
	var scale := float(1<<int(t.level))
	return Vector2(-1.0+2.0*(t.x+x)/scale,-1.0+2.0*(t.y+y)/scale)

static func tile_direction(t: Dictionary,x: float,y: float) -> PackedFloat64Array:
	# Do not round the fractional address through Vector2 in a standard build.
	var scale := float(1<<int(t.level))
	return direction(t.face,-1.0+2.0*(t.x+x)/scale,-1.0+2.0*(t.y+y)/scale)
