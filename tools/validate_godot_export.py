# SPDX-License-Identifier: GPL-3.0-or-later
"""Check exported geometry, instance IDs/scale and glTF asset integrity."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'godot/assets/generated'
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,help='Packed review path, if it was exported from outside this checkout')
args=parser.parse_args()
data=json.loads((BASE/'manifest.json').read_text());report={'schema':1,'sites':{},'prototypes':{},'source_sha256':data['source_sha256']}
source=args.source or ROOT/data['source']
assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()==data['source_sha256'],'Blender source changed'
for key,record in data['prototypes'].items():
    raw=(BASE/record['file']).read_bytes();assert raw[:4]==b'glTF';length,kind=struct.unpack_from('<II',raw,12)
    gltf=json.loads(raw[20:20+length]);assert len(gltf['scenes'])==1 and len(gltf['nodes'])==1,(key,'Unexpected extra exported objects')
    triangles=sum(gltf['accessors'][p['indices']]['count']//3 for mesh in gltf['meshes'] for p in mesh['primitives'])
    assert triangles>0 and triangles<=record['triangles'],(key,triangles,record['triangles'])
    assert all(not any(m.get('emissiveFactor',[0,0,0])) for m in gltf.get('materials',[])),key
    if record['kind']!='GRASS':assert len(gltf.get('images',[]))>0,(key,'Scanned texture maps missing')
    report['prototypes'][key]={'triangles':triangles,'source_triangles':record['triangles'],
        'embedded_images':len(gltf.get('images',[])),'bytes':len(raw)}
for name,site in data['sites'].items():
    tris=0;vertices=0;instances=0;ids=[];counts={}
    for chunk in site['terrain']:
        raw=(BASE/chunk['file']).read_bytes();n,ni=struct.unpack_from('<II',raw)
        assert len(raw)==8+n*48+ni*4 and ni%3==0
        attributes=np.frombuffer(raw,dtype='<f4',count=n*12,offset=8)
        indices=np.frombuffer(raw,dtype='<i4',offset=8+n*48)
        assert np.isfinite(attributes).all() and indices.min()>=0 and indices.max()<n
        assert ni//3==chunk['triangles'];tris+=ni//3;vertices+=n
    for record in site['instances']:
        raw=(BASE/record['file']).read_bytes();n=struct.unpack_from('<I',raw)[0]
        assert len(raw)==4+n*52 and n==record['count']
        transforms=np.frombuffer(raw,dtype='<f4',count=n*12,offset=4).reshape(-1,12)
        assert np.isfinite(transforms).all()
        scales=np.linalg.norm(transforms[:,:9].reshape(-1,3,3),axis=2)
        assert (scales>0).all() and (scales<1000).all(),(name,record['kind'],'Invalid physical scale')
        placement_ids=np.frombuffer(raw,dtype='<i4',offset=4+n*48);ids.extend(int(x) for x in placement_ids)
        counts[record['kind']]=counts.get(record['kind'],0)+n;instances+=n
    assert counts==site['counts'];assert len(ids)==len(set(ids)),(name,'Duplicate plant IDs')
    assert tris<=site['source_terrain_triangles']
    report['sites'][name]={'triangles':tris,'vertices':vertices,'instances':instances,'counts':counts,
        'unique_instance_ids':len(set(ids)),'terrain_chunks':len(site['terrain']),
        'instance_id_sha256':hashlib.sha256(np.asarray(sorted(ids),dtype='<i4').tobytes()).hexdigest()}
out=ROOT/'output/godot-export-checks.json';out.write_text(json.dumps(report,indent=2))
print(json.dumps({k:{'triangles':v['triangles'],'instances':v['instances'],'chunks':v['terrain_chunks']} for k,v in report['sites'].items()},indent=2))
print('GODOT_EXPORT_CHECKS_COMPLETE')
