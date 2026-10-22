# SPDX-License-Identifier: GPL-3.0-or-later
"""Read actual scene-linear EXR masters, including intended-size rotations."""
import json
from pathlib import Path
import bpy,numpy as np
OUT=Path(__file__).resolve().parents[1]/'output/foliage-parity'
def read(path):
    image=bpy.data.images.load(str(path),check_existing=False)
    w,h=image.size;data=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(data)
    bpy.data.images.remove(image);return data.reshape(h,w,4)[:,:,:3]
records=[]
for folder in [OUT]+sorted(p for p in OUT.iterdir() if p.is_dir() and p.name.endswith('-112')):
    reports=list(folder.glob('capture_fix_*_report.json'))
    for path in reports:
        settings=json.loads(path.read_text());kind=settings['kind'].lower()
        for level in sorted(set(row['level'] for row in settings['renders'])):
            for light in sorted(set(row['lighting'] for row in settings['renders'])):
                row={'case':folder.name,'kind':kind,'level':level,'lighting':light,
                     'resolution':settings['resolution'],'rotation_degrees':settings.get('rotation_degrees',0)}
                variants=('baseline','capture_fix')+ (('capture_support',) if (folder/f'capture_support_{kind}_lod{level}_{light}_eevee.exr').exists() else ())
                for variant in variants:
                    a,b=[read(folder/f'{variant}_{kind}_lod{level}_{light}_{engine}.exr') for engine in ('eevee','cycles')]
                    delta=np.abs(a-b);h,w=a.shape[:2]
                    crop=delta[round(h*70/640):round(h*550/640),round(w*.25):round(w*.75)]
                    row[variant]={'linear_rgb_mae':float(delta.mean()),'linear_rgb_p95':float(np.percentile(delta,95)),
                        'linear_normalized_mae':float(delta.mean()/max((a.mean()+b.mean())*.5,1e-8)),
                        'linear_tree_region_mae':float(crop.mean())}
                records.append(row)
(OUT/'linear_benchmarks.json').write_text(json.dumps(records,indent=2))
print('LINEAR_BENCHMARKS_COMPLETE',len(records),flush=True)
