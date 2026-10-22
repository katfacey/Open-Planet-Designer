# SPDX-License-Identifier: GPL-3.0-or-later
"""Fast native regression tests for repair scope, outward maps and exceptions."""
import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from open_planet_lab import foliage
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;root=bpy.data.objects.new('Foliage test root',None);s.collection.objects.link(root)
root['look_foliage_enabled']=True
names=['OP_'+kind+'_LOD2' for kind in sorted(foliage.KINDS)]+['OP_FIR_LOD0']
with bpy.data.libraries.load(str(ROOT/'open_planet_lab/assets/realism_library.blend'),link=False) as (src,dst):dst.objects=names
for ob in dst.objects:
    s.collection.objects.link(ob);ob.parent=root;ob['op_role']='BIOME_SOURCE';ob.hide_render=True
checks={}
def check(name,value):
    checks[name]=bool(value);print('FOLIAGE_NATIVE_CHECK',name,bool(value),flush=True)
    assert value,name
def links(mat):
    return sorted((l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links)
models=foliage.sources(root);original={o.name:o.data for o in models}
mats={m for ob in models for m in ob.data.materials};original_links={m.name:links(m) for m in mats}
detailed=dst.objects[-1];detailed_links=[links(m) for m in detailed.data.materials]
alpha_hash={m.name:hash(foliage.pixels(foliage.atlas(m,'color'))[:,:,3].tobytes()) for m in mats}
foliage.patch_sources(root);foliage.patch_sources(root)
print('FOLIAGE_MAP_DIAGNOSTICS',root.get('op_foliage_status'),flush=True)
for m in mats:
    if not m.node_tree.nodes.get(foliage.FIX):
        print('UNREPAIRED_MAP',m.name,'alpha_max',float(foliage.pixels(foliage.atlas(m,'color'))[:,:,3].max()),flush=True)
check('visible legacy maps repaired once',len(mats)==21 and all(sum(n.name==foliage.FIX for n in m.node_tree.nodes)==1
      for m in mats if foliage.pixels(foliage.atlas(m,'color'))[:,:,3].max()>.5))
check('detailed foliage PBR untouched',[links(m) for m in detailed.data.materials]==detailed_links)
check('atlas alpha bit identical',all(hash(foliage.pixels(foliage.atlas(m,'color'))[:,:,3].tobytes())==alpha_hash[m.name] for m in mats))
counts=(len(bpy.data.objects),len(bpy.data.curves),len(bpy.data.meshes))
with foliage.capture_sources(root) as stats:
    check('seven tessellated alpha supports',len(stats)==7 and all(x['support_triangles']>6 for x in stats))
check('success restores source identity',all(o.data==original[o.name] for o in models))
check('success cleans temporary data',counts==(len(bpy.data.objects),len(bpy.data.curves),len(bpy.data.meshes)))
try:
    with foliage.capture_sources(root):raise RuntimeError('Injected bake failure')
except RuntimeError as error:check('bake error propagated',str(error)=='Injected bake failure')
check('bake failure restores and cleans',all(o.data==original[o.name] for o in models) and counts==(len(bpy.data.objects),len(bpy.data.curves),len(bpy.data.meshes)))
uv=models[-1].data.uv_layers.active.data[0];saved_uv=uv.uv.copy();uv.uv.x=.123
try:
    with foliage.capture_sources(root):raise AssertionError('Edited UV was accepted')
except ValueError as error:check('unsupported UV edit reported','Unsupported edited crown UVs' in str(error))
finally:uv.uv=saved_uv
check('partial build failure restores and cleans',all(o.data==original[o.name] for o in models) and counts==(len(bpy.data.objects),len(bpy.data.curves),len(bpy.data.meshes)))
foliage.restore(root)
check('restore exact original normal links',all(links(m)==original_links[m.name] for m in mats))
check('restore clears mode',not root['look_foliage_enabled'])
test=models[0];material=test.data.materials[0];image=foliage.atlas(material,'normal')
outward=bpy.data.images.new('Test outward normal',width=image.size[0],height=image.size[1],alpha=True)
outward.filepath='//test_outward_normal.png';outward.colorspace_settings.name='Non-Color'
data=foliage.pixels(image);data[:,:,2]=1.-data[:,:,2];outward.pixels.foreach_set(data.ravel())
node=next(n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image==image);node.image=outward
root['look_foliage_enabled']=True;foliage.patch_sources(root)
check('outward atlas never double flipped',material.node_tree.nodes.get(foliage.FIX) is None)
foliage.restore(root);node.image=image;material['op_atlas_normal_convention']='TANGENT_OUTWARD_Z_V1'
root['look_foliage_enabled']=True;foliage.patch_sources(root)
check('new atlas convention honored',material.node_tree.nodes.get(foliage.FIX) is None)
del material['op_atlas_normal_convention'];foliage.restore(root)
check('all runtime proxies remain six triangles',all(len(o.data.polygons)==3 and len(o.data.vertices)==12 for o in models))
out=ROOT/'output/foliage-parity/native_checks.json';out.parent.mkdir(exist_ok=True,parents=True)
out.write_text(json.dumps({'checks':checks,'capture_support':stats},indent=2))
print('FOLIAGE_NATIVE_COMPLETE',flush=True)
