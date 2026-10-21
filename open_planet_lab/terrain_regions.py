# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, non-repeating elevation regions with physical source metadata."""
import json, math
from pathlib import Path
import bpy
import numpy as np
from . import lod_mesh

DATA=Path(__file__).parent/'assets/terrain/regions'
_cache={}

def configure(scene,root):
    """Anchor data to authored sites once; camera movement never moves a region."""
    from mathutils import Vector
    if root.get('op_terrain_regions'):return
    configured=[]
    for site,name in (('Alpine','rainier'),('Desert','canyon')):
        cam=next((o for o in scene.objects if o.type=='CAMERA' and o.get('op_biome_site')==site),None)
        if not cam or not cam.get('op_site_direction'):continue
        center=Vector(cam['op_site_direction']).normalized();east=Vector((0,0,1)).cross(center).normalized();north=center.cross(east).normalized()
        configured.append(dict(name=name,center=list(center),east=list(east),north=list(north)))
    if configured:
        from . import biome
        points,_=biome.sample(scene,root,[tuple(x['center']) for x in configured])
        for region,point in zip(configured,points):
            meta=metadata(region['name']);im=image(region['name']);width,height=im.size
            value=im.pixels[((height//2)*width+width//2)*4]
            source=meta['height_min_m']+value*(meta['height_max_m']-meta['height_min_m'])
            # Relocate the region vertically to the fictional planet's local
            # datum. Preserve every source height DIFFERENCE in real meters.
            region['height_offset_m']=(point.length-1.)*6371000.-source
    root['op_terrain_regions']=json.dumps(configured);root['op_physical_radius_m']=6371000.

def regions(root):
    return json.loads(root.get('op_terrain_regions','[]')) if root.get('biome_realism') else []

def metadata(name):
    return json.loads((DATA/(name+'.json')).read_text())

def image(name):
    path=str(DATA/(name+'.png'))
    im=bpy.data.images.load(path,check_existing=True);im.colorspace_settings.name='Non-Color'
    if not im.packed_file:im.pack()
    return im

def apply_field(g,v,p,height,relief):
    root=getattr(g,'root',None)
    if root is None:return height,relief
    for region in regions(root):
        name=region['name'];meta=metadata(name);delta=g.vec('SUBTRACT',v,tuple(region['center']))
        scale=float(root.get('op_physical_radius_m',6371000.))/meta['width_m']
        u=g.math('MULTIPLY_ADD',g.vec('DOT_PRODUCT',delta,tuple(region['east'])),scale,.5)
        w=g.math('MULTIPLY_ADD',g.vec('DOT_PRODUCT',delta,tuple(region['north'])),scale,.5)
        edge=g.math('MINIMUM',g.math('MINIMUM',u,w),g.math('MINIMUM',g.math('SUBTRACT',1.,u),g.math('SUBTRACT',1.,w)))
        mask=g.smooth(edge,0.,.16)
        if g.tree.bl_idname=='GeometryNodeTree':
            tex=g.node('GeometryNodeImageTexture','Physical USGS region '+name,interpolation='Linear',extension='EXTEND');tex.inputs['Image'].default_value=image(name)
        else:
            tex=g.node('ShaderNodeTexImage','Physical USGS region '+name);tex.image=image(name);tex.extension='EXTEND'
        g.put(g.combine(u,w,0.),tex.inputs['Vector'])
        elevation=g.math('MULTIPLY_ADD',tex.outputs['Color'],meta['height_max_m']-meta['height_min_m'],meta['height_min_m'])
        elevation=g.math('ADD',g.math('MULTIPLY',elevation,p['biome_region_strength']),region.get('height_offset_m',0.))
        elevation=g.math('DIVIDE',elevation,float(root.get('op_physical_radius_m',6371000.)))
        height=g.math('ADD',g.math('MULTIPLY',g.math('SUBTRACT',1.,mask),height),g.math('MULTIPLY',mask,elevation))
        relief=g.math('ADD',g.math('MULTIPLY',g.math('SUBTRACT',1.,mask),relief),g.math('MULTIPLY',mask,tex.outputs['Color']))
    return height,relief

def height_sampler(root,fallback):
    """Height-aware refinement guide; final displacement remains in shared GN."""
    descriptors=[];physical=float(root.get('op_physical_radius_m',6371000.))
    for region in regions(root):
        name=region['name'];meta=metadata(name);key=(name,tuple(meta['resolution']))
        if key not in _cache:
            im=image(name);pixels=np.empty(im.size[0]*im.size[1]*4,dtype=np.float32);im.pixels.foreach_get(pixels)
            values=pixels.reshape(im.size[1],im.size[0],4)[:,:,0].copy()
            # Small conservative height range pyramid for relief-sensitive LOD.
            minima=[values];maxima=[values]
            while min(minima[-1].shape)>=4:
                lo=minima[-1];hi=maxima[-1];h,w=lo.shape;h-=h%2;w-=w%2
                minima.append(lo[:h,:w].reshape(h//2,2,w//2,2).min((1,3)))
                maxima.append(hi[:h,:w].reshape(h//2,2,w//2,2).max((1,3)))
            _cache[key]=(values,minima,maxima)
        descriptors.append((region,meta,_cache[key]))
    strength=float(root.get('biome_region_strength',1.))
    def sample(direction,span=0.):
        value=fallback;relief=0.
        for region,meta,(data,minima,maxima) in descriptors:
            d=tuple(direction[j]-region['center'][j] for j in range(3));scale=physical/meta['width_m']
            u=.5+sum(d[j]*region['east'][j] for j in range(3))*scale
            v=.5+sum(d[j]*region['north'][j] for j in range(3))*scale
            edge=min(u,v,1-u,1-v)
            if edge<0:continue
            mask=lod_mesh.smooth(edge/.16);h,w=data.shape
            # Blender image textures use texel-center coordinates.
            x=max(0.,min(w-1.,u*w-.5));y=max(0.,min(h-1.,v*h-.5));ix=int(x);iy=int(y);fx=x-ix;fy=y-iy
            norm=float((data[iy,ix]*(1-fx)+data[iy,min(ix+1,w-1)]*fx)*(1-fy)+(data[min(iy+1,h-1),ix]*(1-fx)+data[min(iy+1,h-1),min(ix+1,w-1)]*fx)*fy)
            elevation=((norm*(meta['height_max_m']-meta['height_min_m'])+meta['height_min_m'])*strength+region.get('height_offset_m',0.))/physical
            value=value*(1-mask)+(1+elevation)*mask
            if span:
                width=max(1.,span*scale*w);level=min(len(minima)-1,max(0,int(math.log2(width))))
                lo=minima[level];hi=maxima[level];hh,ww=lo.shape;rad=span*scale*.8
                x0=max(0,int((u-rad)*ww));x1=min(ww,int((u+rad)*ww)+2);y0=max(0,int((v-rad)*hh));y1=min(hh,int((v+rad)*hh)+2)
                if x1>x0 and y1>y0:relief=max(relief,float(hi[y0:y1,x0:x1].max()-lo[y0:y1,x0:x1].min())*(meta['height_max_m']-meta['height_min_m'])*strength/physical)
        return value,relief
    return sample if descriptors else None
