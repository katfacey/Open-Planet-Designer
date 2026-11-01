# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract native glTF resources and deduplicate embedded CC0 texture bytes."""
import hashlib,json,shutil,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'godot/assets/generated';DEST=ROOT/'godot/assets/catalog'
(DEST/'textures').mkdir(parents=True,exist_ok=True);(DEST/'models').mkdir(exist_ok=True)
source=json.loads((SOURCE/'manifest.json').read_text());records={};textures={}
kinds={'TREE','TREE_B','TREE_C','SAPLING','FIR','DEAD','ROCK','GRASS','FERN','WILDGRASS'}
for key,record in source['prototypes'].items():
    if record['kind'] not in kinds:continue
    path=SOURCE/record['file'];raw=path.read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+size]);binary=raw[28+size:]
    image_views=set()
    for image in doc.get('images',[]):
        index=image.pop('bufferView');image_views.add(index);view=doc['bufferViews'][index]
        data=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
        digest=hashlib.sha256(data).hexdigest();ext='.png' if image.pop('mimeType')=='image/png' else '.jpg'
        target=DEST/'textures'/(digest+ext)
        if not target.exists():target.write_bytes(data)
        image['uri']='../textures/'+target.name;textures[digest]={'file':'textures/'+target.name,'bytes':len(data)}
    views=[];mapping={};buffer=bytearray()
    for index,view in enumerate(doc['bufferViews']):
        if index in image_views:continue
        offset=view.get('byteOffset',0);block=binary[offset:offset+view['byteLength']]
        mapping[index]=len(views);views.append({**view,'buffer':0,'byteOffset':len(buffer)})
        buffer.extend(block);buffer.extend(bytes((-len(buffer))%4))
    def remap(value):
        if isinstance(value,dict):
            for name,item in value.items():
                if name=='bufferView':value[name]=mapping[item]
                else:remap(item)
        elif isinstance(value,list):
            for item in value:remap(item)
    doc.pop('bufferViews');remap(doc);doc['bufferViews']=views
    name=key.lower();doc['buffers']=[{'byteLength':len(buffer),'uri':name+'.bin'}]
    (DEST/'models'/(name+'.bin')).write_bytes(buffer)
    (DEST/'models'/(name+'.gltf')).write_text(json.dumps(doc,separators=(',',':')))
    records[key]={**record,'file':'models/'+name+'.gltf','source_glb_sha256':hashlib.sha256(raw).hexdigest()}
shutil.copytree(SOURCE/'scans',DEST/'scans',dirs_exist_ok=True)
(DEST/'catalog.json').write_text(json.dumps({'schema':1,'source_manifest_sha256':hashlib.file_digest((SOURCE/'manifest.json').open('rb'),'sha256').hexdigest(),
    'license':'CC0 source scans; project-derived content GPL-3.0-or-later; see THIRD_PARTY_NOTICES.md','prototypes':records,'textures':textures},indent=2))
print(json.dumps({'models':len(records),'unique_textures':len(textures),'texture_bytes':sum(t['bytes'] for t in textures.values())}))
