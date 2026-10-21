"""U.S. terrain tiles: public-domain USGS elevations, repackaged by Mapzen."""
from pathlib import Path
import urllib.request,gzip,math,json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'open_planet_lab/assets/terrain';OUT.mkdir(exist_ok=True)
credits=[]
for tile,name in (('N46W122','rainier'),('N36W113','grand_canyon')):
    url='https://elevation-tiles-prod.s3.amazonaws.com/skadi/'+tile[:3]+'/'+tile+'.hgt.gz'
    raw=gzip.decompress(urllib.request.urlopen(url,timeout=90).read());n=math.isqrt(len(raw)//2)
    data=np.frombuffer(raw,dtype='>i2').reshape(n,n).astype(np.float32)
    valid=data[data>-32000];lo=float(valid.min());hi=float(valid.max());data=np.maximum(data,lo)
    image=Image.fromarray(np.uint16(np.clip((data-lo)/(hi-lo),0,1)*65535))
    image=image.resize((2048,2048),Image.Resampling.BILINEAR);image.save(OUT/(name+'.png'))
    credits.append({'name':name,'tile':tile,'download':url,'height_min_m':lo,'height_max_m':hi,
        'source':'Mapzen Terrain Tiles, U.S. Geological Survey 3DEP/NED elevations',
        'license':'USGS public domain; Mapzen attribution retained',
        'attribution':'Mapzen; 3DEP data courtesy of the U.S. Geological Survey',
        'license_source':'https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
        'modifications':'Resampled to 2048 square and normalized to 16-bit height; artistically remapped in the generator. Not a geographic reconstruction.'})
    print(name,n,lo,hi,flush=True)
(OUT/'CREDITS.json').write_text(json.dumps(credits,indent=2))
