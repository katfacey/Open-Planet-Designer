# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
## Integer hashing + scalar interpolation; no float32 absolute shader coordinates.

static func hash3(x: int,y: int,z: int,seed: int) -> float:
	var h: int=((x&0x7fffffff)*73856093)^((y&0x7fffffff)*19349663)^((z&0x7fffffff)*83492791)^seed
	h=((h^(h>>13))&0x7fffffff)
	h=(h*1274126177)&0x7fffffff
	return float(h)/1073741823.5-1.0

static func sample(x: float,y: float,z: float,seed: int) -> PackedFloat64Array:
	var ix := int(floor(x)); var iy := int(floor(y)); var iz := int(floor(z))
	var fx := x-floorf(x); var fy := y-floorf(y); var fz := z-floorf(z)
	var u := fx*fx*(3.0-2.0*fx); var v := fy*fy*(3.0-2.0*fy); var w := fz*fz*(3.0-2.0*fz)
	var du := 6.0*fx*(1.0-fx); var dv := 6.0*fy*(1.0-fy); var dw := 6.0*fz*(1.0-fz)
	var a := hash3(ix,iy,iz,seed); var b := hash3(ix+1,iy,iz,seed)
	var c := hash3(ix,iy+1,iz,seed); var d := hash3(ix+1,iy+1,iz,seed)
	var e := hash3(ix,iy,iz+1,seed); var f := hash3(ix+1,iy,iz+1,seed)
	var g := hash3(ix,iy+1,iz+1,seed); var h := hash3(ix+1,iy+1,iz+1,seed)
	var ab := lerpf(a,b,u); var cd := lerpf(c,d,u); var ef := lerpf(e,f,u); var gh := lerpf(g,h,u)
	return PackedFloat64Array([lerp(lerp(ab,cd,v),lerp(ef,gh,v),w),
		lerp(lerp(b-a,d-c,v),lerp(f-e,h-g,v),w)*du,
		lerp(cd-ab,gh-ef,w)*dv,(lerp(ef,gh,v)-lerp(ab,cd,v))*dw])
