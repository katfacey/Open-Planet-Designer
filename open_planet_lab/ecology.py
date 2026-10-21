# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic habitat cells shared by explicit plants and distant canopy.

Hash arithmetic stays below 2**24 so Blender's float shader implementation can
reproduce integer results. Geometry and appearance select the same trees.
"""
import math
from . import lod_mesh

PRIME=4093
TREE_KINDS=('TREE','TREE_B','TREE_C','SAPLING','SAPLING_B','FIR','DEAD')

def cell_hash(a,b,face,seed,salt=0):
    h=((a%PRIME)*13+(b%PRIME)*17+face*107+int(seed)*31+salt*109)%PRIME
    return ((h*h)%PRIME)/PRIME

def cell_id(a,b,face,seed):
    return (a*73856093 ^ b*19349663 ^ face*83492791 ^ int(seed)*2654435761)&0xffffffff

def profile(a,b,face,seed):
    age=cell_hash(a,b,face,seed,3)
    if age<.18: kind='SAPLING';factor=.12+.12*cell_hash(a,b,face,seed,4)
    elif age<.29: kind='SAPLING_B';factor=.22+.17*cell_hash(a,b,face,seed,4)
    elif age<.46: kind='FIR';factor=.35+.24*cell_hash(a,b,face,seed,4)
    elif age>.96: kind='DEAD';factor=.65+.35*cell_hash(a,b,face,seed,4)
    else: kind=('TREE','TREE_B','TREE_C')[int(cell_hash(a,b,face,seed,5)*3)%3];factor=.74+.5*cell_hash(a,b,face,seed,4)
    return kind,factor

def patch_density(a,b,face,seed):
    return .20+.80*cell_hash(a//8,b//8,face,seed,9)

def cell(a,b,face,count,seed):
    step=2./count
    u=-1+(a+.12+.76*cell_hash(a,b,face,seed,1))*step
    v=-1+(b+.12+.76*cell_hash(a,b,face,seed,2))*step
    return lod_mesh.unit(lod_mesh.cube_key(face,u,v,1.))

def tree_cells(center,height,reach,seed,forward=None):
    spacing=height*.34;count=max(2,math.ceil(2./spacing));step=2./count
    extent=min(1200,math.ceil(reach/step*2.1)+3)
    x,y,z=center;projections=((x,y,z),(-x,-y,z),(y,-x,z),(-y,x,z),(z,x,y),(-z,x,-y))
    for face,(den,u,v) in enumerate(projections):
        if den<=0:continue
        u/=den;v/=den
        if abs(u)>1+reach*3 or abs(v)>1+reach*3:continue
        ix=int((u+1)/step);iy=int((v+1)/step)
        for a in range(max(0,ix-extent),min(count,ix+extent+1)):
            for b in range(max(0,iy-extent),min(count,iy+extent+1)):
                direction=cell(a,b,face,count,seed)
                delta=tuple(direction[j]-center[j] for j in range(3))
                if sum(t*t for t in delta)>reach*reach:continue
                if forward and sum(delta[j]*forward[j] for j in range(3)) < -height*2:continue
                kind,factor=profile(a,b,face,seed)
                yield direction,cell_id(a,b,face,seed),cell_hash(a,b,face,seed,7),kind,factor,patch_density(a,b,face,seed)

def graph_canopy(g,v,p,forest=1.):
    """Crown envelope of the same seeded cells; no camera-dependent reseeding."""
    def select(mask,a,b):return g.math('ADD',g.math('MULTIPLY',mask,a),g.math('MULTIPLY',g.math('SUBTRACT',1.,mask),b))
    def mod(a,b):return g.math('FLOORED_MODULO',a,b)
    def hashed(a,b,face,salt):
        h=mod(g.math('ADD',g.math('ADD',g.math('MULTIPLY',mod(a,PRIME),13.),g.math('MULTIPLY',mod(b,PRIME),17.)),
                    g.math('ADD',g.math('MULTIPLY',face,107.),g.math('ADD',g.math('MULTIPLY',g.math('FLOOR',p['seed']),31.),salt*109.))),PRIME)
        return g.math('DIVIDE',mod(g.math('MULTIPLY',h,h),PRIME),PRIME)
    x,y,z=g.xyz(v);ax=g.math('ABSOLUTE',x);ay=g.math('ABSOLUTE',y);az=g.math('ABSOLUTE',z)
    xm=g.math('MULTIPLY',g.math('GREATER_THAN',ax,ay),g.math('GREATER_THAN',ax,az))
    ym=g.math('MULTIPLY',g.math('SUBTRACT',1.,xm),g.math('GREATER_THAN',ay,az));zm=g.math('SUBTRACT',1.,g.math('ADD',xm,ym))
    sx=select(g.math('GREATER_THAN',x,0.),1.,-1.);sy=select(g.math('GREATER_THAN',y,0.),1.,-1.);sz=select(g.math('GREATER_THAN',z,0.),1.,-1.)
    den=g.math('MAXIMUM',g.math('MAXIMUM',ax,ay),az)
    u=g.math('DIVIDE',g.math('ADD',g.math('ADD',g.math('MULTIPLY',xm,g.math('MULTIPLY',y,sx)),g.math('MULTIPLY',ym,g.math('MULTIPLY',x,g.math('MULTIPLY',sy,-1.)))),g.math('MULTIPLY',zm,x)),den)
    w=g.math('DIVIDE',g.math('ADD',g.math('MULTIPLY',g.math('ADD',xm,ym),z),g.math('MULTIPLY',zm,g.math('MULTIPLY',y,sz))),den)
    face=g.math('ADD',g.math('ADD',g.math('MULTIPLY',xm,g.math('LESS_THAN',x,0.)),g.math('MULTIPLY',ym,g.math('ADD',2.,g.math('LESS_THAN',y,0.)))),g.math('MULTIPLY',zm,g.math('ADD',4.,g.math('LESS_THAN',z,0.))))
    count=g.math('CEIL',g.math('DIVIDE',2.,g.math('MULTIPLY',p['biome_tree_height'],.34)));step=g.math('DIVIDE',2.,count)
    ia=g.math('FLOOR',g.math('DIVIDE',g.math('ADD',u,1.),step));ib=g.math('FLOOR',g.math('DIVIDE',g.math('ADD',w,1.),step))
    height=0.;coverage=0.
    for du,dv in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,0),(0,1),(1,-1),(1,0),(1,1)):
        a=g.math('ADD',ia,du);b=g.math('ADD',ib,dv)
        cu=g.math('ADD',-1.,g.math('MULTIPLY',g.math('ADD',a,g.math('MULTIPLY_ADD',hashed(a,b,face,1),.76,.12)),step))
        cv=g.math('ADD',-1.,g.math('MULTIPLY',g.math('ADD',b,g.math('MULTIPLY_ADD',hashed(a,b,face,2),.76,.12)),step))
        point=g.combine(g.math('ADD',g.math('ADD',g.math('MULTIPLY',xm,sx),g.math('MULTIPLY',ym,g.math('MULTIPLY',cu,g.math('MULTIPLY',sy,-1.)))),g.math('MULTIPLY',zm,cu)),
                        g.math('ADD',g.math('ADD',g.math('MULTIPLY',xm,g.math('MULTIPLY',cu,sx)),g.math('MULTIPLY',ym,sy)),g.math('MULTIPLY',zm,g.math('MULTIPLY',cv,sz))),
                        g.math('ADD',g.math('MULTIPLY',g.math('ADD',xm,ym),cv),g.math('MULTIPLY',zm,sz)))
        point=g.vec('NORMALIZE',point);age=hashed(a,b,face,3);variation=hashed(a,b,face,4)
        factor=g.math('MULTIPLY_ADD',variation,.5,.74)
        factor=select(g.math('LESS_THAN',age,.46),g.math('MULTIPLY_ADD',variation,.24,.35),factor)
        factor=select(g.math('LESS_THAN',age,.29),g.math('MULTIPLY_ADD',variation,.17,.22),factor)
        factor=select(g.math('LESS_THAN',age,.18),g.math('MULTIPLY_ADD',variation,.12,.12),factor)
        species=hashed(a,b,face,5)
        mature_width=select(g.math('LESS_THAN',species,1/3),.204,select(g.math('LESS_THAN',species,2/3),.256,.225))
        crown_width=select(g.math('LESS_THAN',age,.46),.303,mature_width)
        size=g.math('MULTIPLY',p['biome_tree_height'],factor)
        r=g.math('DIVIDE',g.vec('DISTANCE',point,v),g.math('MULTIPLY',size,crown_width))
        shape=g.math('POWER',g.math('MAXIMUM',g.math('SUBTRACT',1.,g.math('MULTIPLY',r,r)),0.),.55)
        density=g.math('MULTIPLY_ADD',hashed(g.math('FLOOR',g.math('DIVIDE',a,8.)),g.math('FLOOR',g.math('DIVIDE',b,8.)),face,9),.8,.2)
        accepted=g.math('MULTIPLY',g.math('LESS_THAN',hashed(a,b,face,7),g.math('MULTIPLY',g.math('MULTIPLY',density,forest),p['biome_density'])),g.math('LESS_THAN',age,.96))
        height=g.math('MAXIMUM',height,g.math('MULTIPLY',g.math('MULTIPLY',size,shape),accepted))
        coverage=g.math('MAXIMUM',coverage,g.math('MULTIPLY',g.smooth(shape,0.,.15),accepted))
    return height,coverage
