"""Download bounded USGS elevation exports with physical-scale provenance."""
from pathlib import Path
import json, urllib.request, urllib.parse, hashlib
from io import BytesIO
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'open_planet_lab/assets/terrain/regions'
OUT.mkdir(parents=True,exist_ok=True)
SERVICE='https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer'
# Metric EPSG:3857 extents are converted to physical ground spacing below.
SITES=(('canyon',-112.15,36.10,10000.),('rainier',-121.75,46.85,20000.))
def read(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'OpenPlanetLab/1.3 (USGS public-domain elevation)'}),timeout=180).read()
import math
for name,lon,lat,width_m in SITES:
    radius=6378137.;cos=math.cos(math.radians(lat))
    x=radius*math.radians(lon);y=radius*math.log(math.tan(math.pi/4+math.radians(lat)/2))
    half=width_m/(2*cos);bbox=(x-half,y-half,x+half,y+half)
    query=dict(f='json',bbox=','.join(str(v) for v in bbox),bboxSR=3857,imageSR=3857,size='4096,4096',format='tiff',pixelType='F32',interpolation='RSP_BilinearInterpolation',adjustAspectRatio='false',noData=-999999)
    url=SERVICE+'/exportImage?'+urllib.parse.urlencode(query)
    data=json.loads(read(url))
    if 'href' not in data:raise RuntimeError(data)
    raw=read(data['href']);(ROOT/'research/realism'/(name+'_physical.tif')).write_bytes(raw)
    image=Image.open(BytesIO(raw));height=np.array(image,dtype=np.float32)
    if height.ndim!=2 or np.min(height)<-10000:raise RuntimeError((name,height.shape,float(height.min())))
    lo=float(height.min());hi=float(height.max())
    normalized=np.uint16(np.clip((height-lo)/(hi-lo),0,1)*65535)
    Image.fromarray(normalized).save(OUT/(name+'.png'))
    # Downsampled max-min records preserve physical amplitude for evaluation.
    metadata=dict(name=name,source='USGS 3DEP elevation ImageServer',source_url=SERVICE,request_url=url,
        license='Public domain (USGS 3DEP)',license_url='https://data.usgs.gov/datacatalog/data/USGS%3A3a81321b-c153-416f-98b7-cc8e5f0e17c3',
        center_longitude=lon,center_latitude=lat,width_m=width_m,grid_spacing_m=width_m/4096,
        height_min_m=lo,height_max_m=hi,resolution=list(height.shape),sha256=hashlib.sha256(raw).hexdigest(),
        crs=3857,source_extent=data.get('extent'),retrieved='2026-10-21',
        modifications='Bounded projected export; physical horizontal scale corrected at center latitude; height preserved in meters as 16-bit linear encoding. Source mosaic resolution varies; export pixel spacing is not an accuracy claim.')
    (OUT/(name+'.json')).write_text(json.dumps(metadata,indent=2))
    print('REGIONAL_ELEVATION',name,height.shape,lo,hi,'pixel spacing',width_m/4096,flush=True)
