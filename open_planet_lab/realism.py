# SPDX-License-Identifier: GPL-3.0-or-later
"""Coherent age-structured vegetation; fixed physical footprints at every LOD."""
import math, random
from collections import defaultdict
import bpy
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
from . import biome,ecology,lod_mesh

TREES=set(ecology.TREE_KINDS)

def update(scene,root,cam):
    from .lod import logical_camera
    biome.lighting(scene,root);sources=biome.assets(root);cp,forward=logical_camera(root,cam)
    origin=Vector(tuple(root.get('op_anchor_'+a,0.) for a in 'xyz'));local_camera=cp-origin
    center=cp.normalized();ground,_=biome.sample(scene,root,[tuple(center)]);alt=cp.length-ground[0].length
    reach=min(float(root['biome_range']),float(root['biome_tree_distance']))
    candidates=[];seed=int(root['seed'])
    if alt<reach*1.1:
        for direction,key,prob,kind,size,patch in ecology.tree_cells(tuple(center),float(root['biome_tree_height']),reach,seed,tuple(forward)):
            candidates.append((kind,direction,key,prob,size,patch,reach))
    # Ground cover remains physical-sized. Whole tuft patches are not stretched
    # into giant horizontal blades as their LOD changes.
    for kind,spacing,maximum in (('GRASS',root['biome_grass_height']*.55,root['biome_grass_height']*130),
        ('FERN',root['biome_fern_height']*2.4,root['biome_fern_height']*130),('ROCK',root['biome_rock_size']*7.,root['biome_rock_size']*160)):
        maximum=min(maximum,root['biome_range'])
        if alt>maximum*1.1:continue
        # A nested collection of cells keeps positions unchanged. The wider
        # sampling radius is explicit; sizes and density do not depend on ring.
        for direction,key,prob in nearby_ground(center,spacing,maximum,seed+len(kind)*173,forward):
            candidates.append((kind,direction,key,prob,1.,1.,maximum))
    buckets=defaultdict(list);ranked=[]
    focal=scene.render.resolution_y*scene.render.resolution_percentage/100/(2*math.tan(cam.data.angle_y*.5))
    if candidates:
        points,weights=biome.sample(scene,root,[c[1] for c in candidates],local=True)
        for i,(kind,direction,key,prob,factor,patch,maximum) in enumerate(candidates):
            if weights['land'][i]<.98:continue
            forest=weights['forest'][i]
            if kind in TREES:weight=forest*patch
            elif kind=='GRASS':weight=max(weights['grass'][i],forest*.28)*(.55+.45*lod_mesh.smooth((weights['cover'][i]-.25)/.45))
            elif kind=='FERN':weight=forest*.65*lod_mesh.smooth((weights['cover'][i]-.25)/.45)
            else:weight=max(weights['desert'][i]*.22,weights['mountain'][i]*.35,forest*.018)*(.2+.8*lod_mesh.smooth((weights['cover'][i]-.28)/.45))
            if prob>weight*root['biome_density']:continue
            distance=(points[i]-local_camera).length
            if distance>maximum:continue
            if kind in TREES:size=root['biome_tree_height']*factor;actual=kind
            else:
                size=root[{'GRASS':'biome_grass_height','FERN':'biome_fern_height','ROCK':'biome_rock_size'}[kind]]*random.Random(key).uniform(.65,1.2)
                actual=(('GRASS','WILDGRASS','WILDGRASS_B')[key%3] if kind=='GRASS' else ('FERN','FERN_B','FERN_C')[key%3] if kind=='FERN' else kind)
            pixels=size*focal/max(distance,1e-10)
            if pixels<.6:continue
            # Stagger thresholds by persistent cell identity to avoid an entire
            # distance ring changing representation on the same frame.
            threshold=.85+.30*((key>>12)&65535)/65535
            level=(0 if pixels>650*threshold else 1 if pixels>65*threshold else 2) if kind in TREES else (0 if pixels>50*threshold else 1 if pixels>12*threshold else 2)
            ranked.append((pixels,i,actual,level,size,key,distance))
        ranked.sort(reverse=True)
    budget=int(root['biome_budget']);instance_cap=int(root['biome_instances']);used=0;chosen=0;tree_used=0;ground_used=0
    # A separate floor reserve avoids a small set of high-detail crowns taking
    # all resources. Both branches still share the hard total cap.
    tree_cap=budget*.65 if any(x[2] not in TREES for x in ranked) else budget
    tree_levels=[0,0,0];ground_levels=[0,0,0];counts=defaultdict(int);furthest=defaultdict(float)
    if ranked:
        surface=next(o for o in root.children if o.get('op_role')=='SURFACE')
        bvh=BVHTree.FromObject(surface,bpy.context.evaluated_depsgraph_get())
        for pixels,i,kind,level,size,key,distance in ranked:
            if chosen>=instance_cap:break
            is_tree=kind in TREES
            while level<3:
                cost=sources[(kind,level)]['op_triangles']
                ground_ok=is_tree or level==2 or ground_levels[level]+cost<=budget*(.17 if level==0 else .17)
                if used+cost<=budget and ground_ok and (not is_tree or (tree_used+cost<=tree_cap and (level==2 or tree_levels[level]+cost<=tree_cap*(.48 if level==0 else .35)))):break
                level+=1
            if level==3:continue
            direction=Vector(candidates[i][1]);point=points[i]
            # Canonical height is invariant across camera LOD. Surface normals
            # are taken from actual terrain only for small ground props.
            normal=direction
            if not is_tree:
                hit,n,index,travel=bvh.ray_cast(point+direction*.00003,-direction,.00006)
                if hit is not None and abs((hit-point).dot(direction))<size*.6:normal=n.normalized()
            axis=direction if is_tree else normal
            q=Vector((0,0,1)).rotation_difference(axis)@Quaternion((0,0,1),(key%65536)/65536*math.tau)
            point=point-axis*size*(.025 if is_tree else .04)
            buckets[(kind,level)].append((tuple(point),tuple(q.to_euler()),(size,size,size),key if key<2147483648 else key-4294967296))
            cost=sources[(kind,level)]['op_triangles'];used+=cost;chosen+=1
            if is_tree:tree_used+=cost;tree_levels[level]+=cost
            else:ground_used+=cost;ground_levels[level]+=cost
            counts[kind]+=1;furthest['trees' if is_tree else 'ground']=max(furthest['trees' if is_tree else 'ground'],distance)
    for key,source in sources.items():
        data=buckets[key];ob=biome.emitter(root,source);ob.hide_render=not data;ob.hide_viewport=not data;ob.location=origin
        mesh=ob.data;mesh.clear_geometry();mesh.from_pydata([v[0] for v in data],[],[])
        for name,column in (('op_rotation',1),('op_scale',2)):
            attr=mesh.attributes.get(name) or mesh.attributes.new(name=name,type='FLOAT_VECTOR',domain='POINT')
            if data:attr.data.foreach_set('vector',[x for row in data for x in row[column]])
        ids=mesh.attributes.get('id') or mesh.attributes.new(name='id',type='INT',domain='POINT')
        if data:ids.data.foreach_set('value',[row[3] for row in data])
        mesh.update();ob['op_instance_count']=len(data);ob['op_expanded_triangles']=len(data)*source['op_triangles']
    # Clear old emitters whose kinds are absent from the revised library.
    active={kind+str(level) for kind,level in sources}
    for ob in root.children:
        if ob.get('op_role')=='BIOME_INSTANCES' and ob.get('op_scatter_key') not in active:
            ob.data.clear_geometry();ob.hide_render=True;ob.hide_viewport=True;ob['op_instance_count']=0;ob['op_expanded_triangles']=0
    import json
    root['op_biome_triangles']=used;root['op_biome_instances']=chosen;root['op_ecology_counts']=json.dumps(dict(counts),sort_keys=True)
    root['op_ecology_reach']=json.dumps(dict(furthest));root['op_biome_status']=f'{chosen:,} physical plants/rocks Â· {used:,} triangles Â· {len(counts)} forms'
    biome.lighting(scene,root)

def nearby_ground(center,spacing,radius,seed,forward):
    count=max(2,math.ceil(2./spacing));step=2./count;extent=min(550,math.ceil(radius/step*1.8)+2)
    x,y,z=center;projections=((x,y,z),(-x,-y,z),(y,-x,z),(-y,x,z),(z,x,y),(-z,x,-y))
    for face,(den,u,v) in enumerate(projections):
        if den<=0:continue
        u/=den;v/=den
        if abs(u)>1+radius*3 or abs(v)>1+radius*3:continue
        ix=int((u+1)/step);iy=int((v+1)/step)
        for a in range(max(0,ix-extent),min(count,ix+extent+1)):
            for b in range(max(0,iy-extent),min(count,iy+extent+1)):
                direction=ecology.cell(a,b,face,count,seed);delta=tuple(direction[j]-center[j] for j in range(3))
                if sum(t*t for t in delta)>radius*radius or sum(delta[j]*forward[j] for j in range(3)) < -spacing*2:continue
                yield direction,ecology.cell_id(a,b,face,seed),ecology.cell_hash(a,b,face,seed,7)
