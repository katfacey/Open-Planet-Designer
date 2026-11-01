# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent weighted-corner reference for the native scalar terrain sampler."""
import hashlib,importlib.util,itertools,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cube_reference',ROOT/'open_planet_lab/lod_mesh.py')
cube=importlib.util.module_from_spec(spec);spec.loader.exec_module(cube)
def corner(x,y,z,seed):
    h=((x&0x7fffffff)*73856093)^((y&0x7fffffff)*19349663)^((z&0x7fffffff)*83492791)^seed
    h=(h^(h>>13))&0x7fffffff
    return ((h*1274126177)&0x7fffffff)/1073741823.5-1
def noise(point,seed):
    integers=[math.floor(v) for v in point];fractions=[v-math.floor(v) for v in point]
    weights=[t*t*(3-2*t) for t in fractions];derivatives=[6*t*(1-t) for t in fractions]
    result=[0.,0.,0.,0.]
    for bits in itertools.product((0,1),repeat=3):
        value=corner(*(integers[i]+bits[i] for i in range(3)),seed)
        w=[weights[i] if bits[i] else 1-weights[i] for i in range(3)]
        result[0]+=value*math.prod(w)
        for axis in range(3):result[axis+1]+=value*derivatives[axis]*(1 if bits[axis] else -1)*math.prod(w[i] for i in range(3) if i!=axis)
    return result
cases=[{'point':p,'seed':seed,'sample':noise(p,seed)} for p in [(0.,0.,0.),(-3.125,.17,8.32),(191.3,-47.2,.5),(3000000.125,-2000000.1,-0.125)] for seed in (7,42,2026)]
directions=[{'face':face,'u':u,'v':v,'direction':cube.unit(cube.cube_key(face,u,v,1.))} for face in range(6) for u,v in ((0.,0.),(.08,.11),(-1.,.3),(.99,1.))]
height_cases=[]
for entry in directions:
    d=entry['direction'];height=450.
    for i,(amplitude,length) in enumerate(((800.,524288.),(180.,16384.),(25.,512.),(2.,32.),(.15,2.))):
        height+=amplitude*noise([v*6371000./length for v in d],42+i*701)[0]
    height_cases.append({'direction':d,'height_m':height})
destination=ROOT/'godot/tests/fixtures';destination.mkdir(exist_ok=True)
(destination/'native_scalar.json').write_text(json.dumps({'schema':1,'reference':'Python weighted-corner sum + retained Blender-independent cube mapping','noise':cases,'directions':directions,'heights':height_cases},indent=2))
print(f'Wrote {len(cases)} noise, {len(directions)} cube and {len(height_cases)} height fixtures')
