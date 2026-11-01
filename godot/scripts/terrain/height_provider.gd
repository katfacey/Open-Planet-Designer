# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const Location=preload("res://scripts/world/planet_location.gd")
const FieldNoise=preload("res://scripts/terrain/canonical_noise.gd")
const BANDS=[[800.0,524288.0],[180.0,16384.0],[25.0,512.0],[2.0,32.0],[0.15,2.0]]
var radius_m: float
var seed: int
var sea_level: float
var signature: String
var identity_namespace: String
var regions: Array=[]
var region_metadata: Dictionary={}

func configure(definition: Resource) -> void:
	radius_m=definition.radius_m; seed=definition.seed; sea_level=definition.sea_level_m
	identity_namespace=definition.planet_id+"/"+definition.ecology_revision+"/seed:"+str(seed)
	var source := FileAccess.get_file_as_string(definition.region_manifest) if FileAccess.file_exists(definition.region_manifest) else ""
	signature=(definition.signature()+source).sha256_text()
	if source.is_empty(): return
	region_metadata=JSON.parse_string(source)
	for info in region_metadata.get("regions",[]):
		var entry: Dictionary=info.duplicate(true)
		entry.data=FileAccess.get_file_as_bytes("res://assets/native/"+str(info.file))
		if entry.data.size()!=int(info.size)*int(info.size)*2:
			push_error("Invalid regional height data: "+str(info.name)); continue
		entry.bounds=FileAccess.get_file_as_bytes("res://assets/native/"+str(info.bounds_file))
		if _digest(entry.data)!=str(info.native_sha256) or _digest(entry.bounds)!=str(info.bounds_sha256):
			push_error("Regional data checksum mismatch: "+str(info.name)); continue
		var d := Location.direction(info.face,info.u,info.v)
		var basis := Location.frame(d)
		entry.direction=d; entry.east=basis.x; entry.north=-basis.z
		regions.append(entry)

func sample(d: PackedFloat64Array) -> PackedFloat64Array:
	var x: float=d[0]*radius_m; var y: float=d[1]*radius_m; var z: float=d[2]*radius_m
	var height := 450.0; var gx := 0.0; var gy := 0.0; var gz := 0.0
	for i in BANDS.size():
		var amplitude: float=BANDS[i][0]; var scale: float=BANDS[i][1]
		var n := FieldNoise.sample(x/scale,y/scale,z/scale,seed+i*701)
		height+=n[0]*amplitude; gx+=n[1]*amplitude/scale; gy+=n[2]*amplitude/scale; gz+=n[3]*amplitude/scale
	for region in regions:
		var c: PackedFloat64Array=region.direction
		var limit: float=cos(minf(PI*0.5,float(region.width_m)*0.75/radius_m))
		if d[0]*c[0]+d[1]*c[1]+d[2]*c[2]<maxf(0.0,limit): continue
		var east: Vector3=region.east; var north: Vector3=region.north
		var dx: float=x-c[0]*radius_m; var dy: float=y-c[1]*radius_m; var dz: float=z-c[2]*radius_m
		var u: float=(dx*east.x+dy*east.y+dz*east.z)/float(region.width_m)+0.5
		var v: float=(dx*north.x+dy*north.y+dz*north.z)/float(region.width_m)+0.5
		if u<=0.0 or u>=1.0 or v<=0.0 or v>=1.0: continue
		var edge: float=min(min(u,1.0-u),min(v,1.0-v))
		var blend := smoothstep(0.0,0.16,edge)
		var measured := _region_sample(region,u,v)
		# Differentiate the blend too; normals/collision share the same physical surface.
		var edge_u := 1.0 if u<0.5 else -1.0
		var edge_v := 1.0 if v<0.5 else -1.0
		if min(u,1.0-u)<min(v,1.0-v): edge_v=0.0
		else: edge_u=0.0
		var t: float=clamp(edge/0.16,0.0,1.0)
		var derivative: float=6.0*t*(1.0-t)/0.16/float(region.width_m)
		var difference: float=measured[0]-height
		gx=lerp(gx,measured[1]*east.x+measured[2]*north.x,blend)+difference*derivative*(edge_u*east.x+edge_v*north.x)
		gy=lerp(gy,measured[1]*east.y+measured[2]*north.y,blend)+difference*derivative*(edge_u*east.y+edge_v*north.y)
		gz=lerp(gz,measured[1]*east.z+measured[2]*north.z,blend)+difference*derivative*(edge_u*east.z+edge_v*north.z)
		height=lerp(height,measured[0],blend)
	var habitat := FieldNoise.sample(x/480.0,y/480.0,z/480.0,seed+999)[0]
	var forest := smoothstep(-0.18,0.25,habitat)
	var radial: float=gx*d[0]+gy*d[1]+gz*d[2]
	var factor := radius_m/(radius_m+height)
	var normal := Vector3(d[0]-factor*(gx-radial*d[0]),d[1]-factor*(gy-radial*d[1]),d[2]-factor*(gz-radial*d[2])).normalized()
	return PackedFloat64Array([height,normal.x,normal.y,normal.z,forest,0.35,1.0 if height>sea_level else 0.0,0.0,smoothstep(1400.0,3500.0,height)])

func height(d: PackedFloat64Array) -> float:
	return sample(d)[0]

func position(d: PackedFloat64Array) -> PackedFloat64Array:
	return Location.point(d,radius_m+height(d))

func _region_sample(region: Dictionary,u: float,v: float) -> PackedFloat64Array:
	var size: int=region.size
	# Pixel-centre convention matches the preserved source footprint.
	var px: float=clamp(u*size-0.5,0.0,float(size-1)); var py: float=clamp(v*size-0.5,0.0,float(size-1))
	var ix := int(px); var iy := int(py); var jx := mini(ix+1,size-1); var jy := mini(iy+1,size-1)
	var data: PackedByteArray=region.data
	var a := float(data.decode_u16((iy*size+ix)*2)); var b := float(data.decode_u16((iy*size+jx)*2))
	var c := float(data.decode_u16((jy*size+ix)*2)); var e := float(data.decode_u16((jy*size+jx)*2))
	var scale: float=(float(region.height_max_m)-float(region.height_min_m))/65535.0
	return PackedFloat64Array([lerp(lerp(a,b,px-ix),lerp(c,e,px-ix),py-iy)*scale+float(region.height_min_m)+float(region.height_offset_m),
		lerp(b-a,e-c,py-iy)*scale*size/float(region.width_m),lerp(c-a,e-b,px-ix)*scale*size/float(region.width_m)])

func error_bound(spacing: float, d: PackedFloat64Array) -> float:
	var error := spacing*spacing/(4.0*radius_m)
	for band in BANDS:
		error+=min(2.0*float(band[0]),24.0*float(band[0])*pow(spacing/float(band[1]),2.0))
	for region in regions:
		var c: PackedFloat64Array=region.direction
		var span: float=spacing*32.0
		var separation := acos(clampf(d[0]*c[0]+d[1]*c[1]+d[2]*c[2],-1.0,1.0))
		if separation>(span*2.0+float(region.width_m))/radius_m: continue
		var east: Vector3=region.east; var north: Vector3=region.north
		var dx: float=(d[0]-c[0])*radius_m; var dy: float=(d[1]-c[1])*radius_m; var dz: float=(d[2]-c[2])*radius_m
		var u: float=(dx*east.x+dy*east.y+dz*east.z)/float(region.width_m)+0.5
		var v: float=(dx*north.x+dy*north.y+dz*north.z)/float(region.width_m)+0.5
		var half_width: float=span*2.0/float(region.width_m)
		if u-half_width>1.0 or u+half_width<0.0 or v-half_width>1.0 or v+half_width<0.0: continue
		var range_m := _region_range(region,u,v,half_width)
		var interior: bool=minf(minf(u,1.0-u),minf(v,1.0-v))>0.16+half_width
		if interior:
			var source_spacing: float=float(region.width_m)/float(region.size)
			error=minf(range_m,2.0*range_m*spacing/source_spacing)+spacing*spacing/(4.0*radius_m)
		else:
			# Blend boundaries can mix both providers; retain the combined range.
			var low: float=minf(-557.15,float(region.height_min_m)+float(region.height_offset_m))
			var high: float=maxf(1457.15,float(region.height_max_m)+float(region.height_offset_m))
			error+=high-low
	return error

func _region_range(region: Dictionary,u: float,v: float,half_width: float) -> float:
	var pixels: float=maxf(2.0,half_width*2.0*float(region.size)+4.0)
	var level := clampi(int(floor(log(pixels)/log(2.0)))-1,0,region.bounds_levels.size()-1)
	var info: Dictionary=region.bounds_levels[level]; var size: int=info.size
	var x0 := clampi(int(floor((u-half_width)*size))-1,0,size-1)
	var x1 := clampi(int(ceil((u+half_width)*size))+1,0,size-1)
	var y0 := clampi(int(floor((v-half_width)*size))-1,0,size-1)
	var y1 := clampi(int(ceil((v+half_width)*size))+1,0,size-1)
	var low := 65535; var high := 0; var data: PackedByteArray=region.bounds
	for y in range(y0,y1+1):
		for x in range(x0,x1+1):
			var index: int=int(info.offset)+(y*size+x)*4
			low=mini(low,data.decode_u16(index)); high=maxi(high,data.decode_u16(index+2))
	return float(high-low)/65535.0*(float(region.height_max_m)-float(region.height_min_m))

func _digest(bytes: PackedByteArray) -> String:
	var context := HashingContext.new(); context.start(HashingContext.HASH_SHA256); context.update(bytes)
	return context.finish().hex_encode()
