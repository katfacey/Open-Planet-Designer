# SPDX-License-Identifier: GPL-3.0-or-later
"""Camera-adaptive cube sphere with conforming edges; no Blender dependency.

All six faces use integer cube coordinates. Fine edge vertices are included in
adjacent coarse cell fans, including across cube-face seams, so there are no
T-junctions or skirts to expose during a fly-through.
"""
import bisect
import heapq
import math

def unit(v):
    d=math.sqrt(sum(x*x for x in v));return tuple(x/d for x in v)

def cube_key(face,u,v,scale):
    return ((scale,u,v),(-scale,-u,v),(-u,scale,v),(u,-scale,v),(u,v,scale),(u,-v,-scale))[face]

def smooth(x):
    x=max(0.,min(1.,x));return x*x*(3.-2.*x)

def build(camera, *, radius=1., focal=700., ortho_size=0., pixels=5.,
          near=.004, far=.25, max_depth=18, budget=40000, forward=None,height_guide=None):
    """Distances and output vertices are in planet-radius units.

    Refinement is deterministic and best-first. The mesh always covers the
    complete globe; out-of-view and hidden regions simply stay coarse.
    """
    depth=max(1,min(24,int(max_depth)));scale=1<<depth
    budget=max(48,int(budget))
    cam=tuple(float(x) for x in camera);cam_len=math.sqrt(sum(x*x for x in cam))
    near=max(1e-7,near);far=max(near*1.01,far);pixels=max(.5,pixels)
    def score(cell):
        face,u,v,size,level=cell
        c=unit(cube_key(face,u+size//2,v+size//2,scale));span=2.0*size/scale
        actual_radius,relief=height_guide(c,span) if height_guide else (radius,0.)
        point=tuple(x*actual_radius for x in c)
        delta=tuple(point[i]-cam[i] for i in range(3));dist=max(1e-8,math.sqrt(sum(x*x for x in delta)))
        # Coarse complete backside stays present for off-axis views/reflections.
        if cam_len>radius+span and sum(c[i]*cam[i] for i in range(3)) < radius-span*1.5:return 0.
        if forward and dist>span*2 and sum(delta[i]*forward[i] for i in range(3))/dist < .15-span/dist:return 0.
        fade=smooth((dist-near)/(far-near))
        tolerance=pixels*(1.+7.*fade)
        target=ortho_size*tolerance/max(focal,1.) if ortho_size else dist*tolerance/max(focal,1.)
        return max(span*actual_radius,relief*2.)/max(target,1e-10)
    leaves=set();heap=[];serial=0;live_corners=set()
    for face in range(6):
        cell=(face,-scale,-scale,2*scale,0);leaves.add(cell);heapq.heappush(heap,(-score(cell),serial,cell));serial+=1
        live_corners.update(cube_key(face,u,v,scale) for u,v in ((-scale,-scale),(scale,-scale),(scale,scale),(-scale,scale)))
    while heap:
        neg,_,cell=heapq.heappop(heap)
        if -neg<=1.:break
        if cell[-1]>=depth:continue
        f,u,v,size,level=cell;half=size//2
        additions={cube_key(f,a,b,scale) for a,b in ((u+half,v),(u+size,v+half),(u+half,v+size),(u,v+half),(u+half,v+half))}-live_corners
        # The closed conforming triangular sphere has T=2V-4. Its vertices are
        # exactly the unique cell corners plus one interior center per leaf.
        # Track the true cost instead of reserving six triangles for every leaf.
        new_triangles=2*(len(live_corners)+len(additions)+len(leaves)+3)-4
        if new_triangles>budget:
            if budget-(2*(len(live_corners)+len(leaves))-4)<8:break
            continue
        live_corners.update(additions);leaves.remove(cell)
        for du,dv in ((0,0),(half,0),(half,half),(0,half)):
            child=(f,u+du,v+dv,half,level+1);leaves.add(child)
            heapq.heappush(heap,(-score(child),serial,child));serial+=1
    ordered=sorted(leaves)
    corners=set();cell_corners=[]
    for f,u,v,size,level in ordered:
        ks=[cube_key(f,u,v,scale),cube_key(f,u+size,v,scale),cube_key(f,u+size,v+size,scale),cube_key(f,u,v+size,scale)]
        corners.update(ks);cell_corners.append(ks)
    # Index every straight cube line, including lines shared by two cube faces.
    lines={}
    for key in corners:
        for axis in range(3):
            other=tuple(key[i] for i in range(3) if i!=axis)
            lines.setdefault((axis,other),set()).add(key[axis])
    lines={k:sorted(v) for k,v in lines.items()}
    vertices=[];indices={};faces=[]
    def vertex(key):
        if key not in indices:indices[key]=len(vertices);vertices.append(unit(key))
        return indices[key]
    for cell,ks in zip(ordered,cell_corners):
        f,u,v,size,level=cell;center=vertex(cube_key(f,u+size//2,v+size//2,scale));boundary=[]
        for a,b in zip(ks,ks[1:]+ks[:1]):
            axis=next(i for i in range(3) if a[i]!=b[i]);other=tuple(a[i] for i in range(3) if i!=axis)
            values=lines[(axis,other)];lo=min(a[axis],b[axis]);hi=max(a[axis],b[axis])
            values=values[bisect.bisect_left(values,lo):bisect.bisect_right(values,hi)]
            if b[axis]<a[axis]:values=values[::-1]
            for q in values[:-1]:
                key=list(a);key[axis]=q;boundary.append(vertex(tuple(key)))
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((center,a,b))
    if len(faces)>budget:raise RuntimeError('Adaptive mesh exceeded its triangle budget')
    worst=max(score(cell) for cell in leaves if cell[-1]<depth) if any(c[-1]<depth for c in leaves) else 0.
    return vertices,faces,dict(triangles=len(faces),vertices=len(vertices),leaves=len(leaves),
        deepest=max(c[-1] for c in leaves),budget_limited=worst>1.,worst_error=worst)
