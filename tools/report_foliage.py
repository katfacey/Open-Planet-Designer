# SPDX-License-Identifier: GPL-3.0-or-later
"""Display comparisons and labeled contacts from actual native render outputs."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/foliage-parity'
DOC=ROOT/'docs/media/foliage';DOC.mkdir(exist_ok=True,parents=True)
report=json.loads((OUT/'validation.json').read_text())
for site,record in report.items():
    contact=Image.new('RGB',(1920,1128),(20,24,29));draw=ImageDraw.Draw(contact)
    for row,variant in enumerate(('before','after')):
        pair=[]
        for col,engine in enumerate(('eevee','cycles')):
            path=OUT/('_'.join((site.lower(),variant,engine))+'.png')
            image=Image.open(path).convert('RGB');pair.append(np.asarray(image,dtype=float)/255.)
            contact.paste(image,(col*960,row*564+24))
            draw.text((col*960+10,row*564+6),f'{site} | {variant.upper()} | {engine.upper()} | +3 EV',fill='white')
        a,b=pair;delta=np.abs(a-b)
        record['comparisons'][variant].update(display_rgb_mae_percent=float(delta.mean()*100),
            display_channel_p95_percent=float(np.percentile(delta,95)*100),
            display_signed_bias_percent=float((a-b).mean()*100),
            lower_half_mae_percent=float(delta[270:].mean()*100),
            middle_crop_mae_percent=float(delta[108:432,192:768].mean()*100))
    contact.save(DOC/(site.lower()+'-comparison.jpg'),quality=93)
isolated=[]
for level in range(3):
    for light in ('front','back','overcast'):
        row={'level':level,'light':light}
        for variant in ('baseline','capture_support','capture_fix'):
            pair=[np.asarray(Image.open(OUT/f'{variant}_tree_lod{level}_{light}_{e}.png').convert('RGB'),dtype=float)/255.
                  for e in ('eevee','cycles')]
            delta=np.abs(pair[0]-pair[1]);row[variant]={'display_rgb_mae_percent':float(delta.mean()*100),
                'tree_region_mae_percent':float(delta[70:550,160:480].mean()*100)}
        isolated.append(row)
canvas=Image.new('RGB',(1920,1328),(20,24,29));draw=ImageDraw.Draw(canvas)
for row,variant in enumerate(('baseline','capture_support')):
    for col,(light,engine) in enumerate((('front','cycles'),('overcast','eevee'),('overcast','cycles'))):
        image=Image.open(OUT/f'{variant}_tree_lod2_{light}_{engine}.png').convert('RGB')
        canvas.paste(image,(col*640,row*664+24))
        draw.text((col*640+8,row*664+6),f'{variant.upper()} | {light} | {engine}',fill='white')
canvas.save(DOC/'isolated-comparison.jpg',quality=93)
intended=[]
for folder in sorted(OUT.glob('*-112')):
    kind=folder.name.rsplit('-',2)[0].lower()
    for level in (0,2):
        for light in ('front','back','overcast'):
            row={'case':folder.name,'kind':kind,'level':level,'light':light,'resolution':[112,112]}
            for variant in ('baseline','capture_fix')+ (('capture_support',) if level==2 else ()):
                a,b=[np.asarray(Image.open(folder/f'{variant}_{kind}_lod{level}_{light}_{engine}.png').convert('RGB'),dtype=float)/255.
                     for engine in ('eevee','cycles')]
                delta=np.abs(a-b)
                row[variant]={'display_rgb_mae_percent':float(delta.mean()*100),
                    'tree_region_mae_percent':float(delta[12:96,28:84].mean()*100)}
            intended.append(row)
final={'blender':'5.2.0 LTS','hardware':'RTX 5090; Core i9-14900K; see per-case device',
       'portable_tests':23,'native_checks':json.loads((OUT/'native_checks.json').read_text()),
       'capture_checks':json.loads((OUT/'capture_checks.json').read_text()),
       'linear_benchmarks':json.loads((OUT/'linear_benchmarks.json').read_text()),
       'isolated_tree':isolated,'intended_size':intended,'scenes':report}
final['experimental_above_ground']={}
for site in ('forest','grassland'):
    a,b=[np.asarray(Image.open(OUT/path).convert('RGB'),dtype=float)/255. for path in
         (site+'_above_floor_eevee.png',site+'_after_cycles.png')]
    final['experimental_above_ground'][site]={'display_rgb_mae_percent':float(np.abs(a-b).mean()*100),
        'same_corrected_normals_cycles_reference':True,'default_enabled':False}
(OUT/'measured_results.json').write_text(json.dumps(final,indent=2))
(ROOT/'docs/verification/foliage-development.json').write_text(json.dumps(final,indent=2))
print(json.dumps({site:r['comparisons'] for site,r in report.items()},indent=2))
