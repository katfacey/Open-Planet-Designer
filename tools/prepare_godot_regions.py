# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert preserved 16-bit measured terrain to native, versioned CPU data; no Blender."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'godot/assets/native';DEST.mkdir(parents=True,exist_ok=True)
records=[]
for name,face,u,v,floor in [('rainier',2,.32,.18,300.),('canyon',0,.05,.3,200.)]:
    source=ROOT/'open_planet_lab/assets/terrain/regions'/f'{name}.png'
    meta=json.loads(source.with_suffix('.json').read_text())
    pixels=np.asarray(Image.open(source),dtype=np.uint16)[::-1].copy()
    raw=pixels.astype('<u2').tobytes();(DEST/f'{name}.opheight').write_bytes(raw)
    minima=pixels.copy();maxima=pixels.copy();pyramid=[];offset=0;bounds=bytearray()
    while minima.shape[0]>1:
        h,w=minima.shape
        minima=minima.reshape(h//2,2,w//2,2).min((1,3));maxima=maxima.reshape(h//2,2,w//2,2).max((1,3))
        block=np.stack((minima,maxima),axis=-1).astype('<u2').tobytes()
        pyramid.append({'size':len(minima),'offset':offset,'bytes':len(block)});bounds.extend(block);offset+=len(block)
    (DEST/f'{name}.opbounds').write_bytes(bounds)
    records.append({**meta,'file':f'{name}.opheight','size':pixels.shape[0],'face':face,'u':u,'v':v,
        'height_offset_m':floor-float(meta['height_min_m']),'native_sha256':hashlib.sha256(raw).hexdigest(),
        'source_png_sha256':hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),
        'bounds_file':f'{name}.opbounds','bounds_levels':pyramid,
        'bounds_sha256':hashlib.sha256(bounds).hexdigest(),'no_data_note':'No per-pixel no-data mask survives in the preserved 16-bit PNG; encoded samples are used as supplied.',
        'placement_note':'New native fictional-planet placement; source relief/footprint retained, explicit constant vertical offset; not the Blender camera transform.'})
(DEST/'regions.json').write_text(json.dumps({'schema':1,'encoding':'uint16 little-endian; row zero south; pixel centres','regions':records},indent=2))
print(json.dumps({r['name']:{'width_m':r['width_m'],'size':r['size'],'bytes':(DEST/r['file']).stat().st_size} for r in records}))
