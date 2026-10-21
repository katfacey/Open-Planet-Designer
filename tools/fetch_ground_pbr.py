from pathlib import Path
import urllib.request,json
from fetch_biome_assets import fetch_file,HEADERS
ROOT=Path(__file__).resolve().parents[1]/'open_planet_lab/assets/ground';ROOT.mkdir(exist_ok=True)
credits=[]
for name in ('forrest_ground_01','brown_mud_leaves_01','rock_boulder_dry','leafy_grass'):
    data=json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/'+name,headers=HEADERS)))
    files={}
    for field,key in (('Diffuse','color'),('Displacement','height'),('Rough','roughness')):
        meta=data[field]['2k']['jpg' if field=='Diffuse' else 'png']
        target=ROOT/(name+'_'+key+Path(meta['url']).suffix);fetch_file((target,meta));files[key]=target.name
    item={'asset':name,'source':'https://polyhaven.com/a/'+name,'license':'CC0 1.0',
          'license_url':'https://polyhaven.com/license','files':files}
    (ROOT/(name+'.json')).write_text(json.dumps(item,indent=2));credits.append(item)
name='kloofendal_48d_partly_cloudy_puresky'
data=json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/'+name,headers=HEADERS)))
meta=data['hdri']['2k']['hdr'];fetch_file((ROOT/'sky.hdr',meta))
credits.append({'asset':name,'source':'https://polyhaven.com/a/'+name,'license':'CC0 1.0','license_url':'https://polyhaven.com/license','file':meta})
(ROOT/'CREDITS.json').write_text(json.dumps(credits,indent=2))
