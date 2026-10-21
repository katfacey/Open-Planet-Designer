"""Fetch verified CC0 source models and color/alpha maps from Poly Haven."""
from pathlib import Path
import urllib.request, json, hashlib, sys
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]/'research'/'cc0'
HEADERS={'User-Agent':'OpenPlanetLab/1.2 (CC0 environment assets)'}

def fetch_file(item):
    target,meta=item;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and hashlib.md5(target.read_bytes()).hexdigest()==meta['md5']:return
    with urllib.request.urlopen(urllib.request.Request(meta['url'],headers=HEADERS),timeout=90) as src, target.open('wb') as dst:
        while chunk:=src.read(1024*1024):dst.write(chunk)
    assert hashlib.md5(target.read_bytes()).hexdigest()==meta['md5'],target
    print('Verified',target.name,round(target.stat().st_size/1e6,1),'MB',flush=True)

def main():
    jobs=[];credits=[]
    names=sys.argv[1:] or ('pine_tree_01','grass_medium_01','boulder_01','fern_02')
    previous=json.loads((ROOT/'CREDITS.json').read_text()) if (ROOT/'CREDITS.json').exists() else []
    credits=[c for c in previous if c['asset'] not in names]
    for name in names:
        folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True)
        data=json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/'+name,headers=HEADERS)))
        (folder/'manifest.json').write_text(json.dumps(data,indent=2))
        model=data['blend']['1k']['blend'];jobs.append((folder/(name+'_1k.blend'),model))
        for rel,meta in model.get('include',{}).items():
            if any(s in rel for s in ('_diff_','_alpha_','_rough_','_nor_gl_')):jobs.append((folder/rel,meta))
        credits.append({'asset':name,'source':'https://polyhaven.com/a/'+name,
                        'license':'CC0 1.0','license_url':'https://polyhaven.com/license'})
    (ROOT/'CREDITS.json').write_text(json.dumps(credits,indent=2))
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch_file,jobs))

if __name__=='__main__':main()
