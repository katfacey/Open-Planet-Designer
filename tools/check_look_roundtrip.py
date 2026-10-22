"""Native regression checks: geometry/light cache invalidation and alpha restore."""
import array,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,lookdev
OUT=ROOT/'output/next-realism'
prepare='--prepare' in sys.argv
path=OUT/('daylight_grassland.blend' if prepare else 'cache_roundtrip.blend')
bpy.ops.wm.open_mainfile(filepath=str(path))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'));lod.unregister()
from open_planet_lab.nodes import refresh_loaded_controls
refresh_loaded_controls(r);s.frame_set(s.frame_current);bpy.context.view_layer.update()
if prepare:
    r['lod_enabled']=False
    lookdev.bake(s,r)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'cache_roundtrip.blend'),compress=True)
    print('ROUNDTRIP_FIXTURE_READY',flush=True)
    raise SystemExit(0)
checks={}
def check(name,value):
    checks[name]=bool(value);print('ROUNDTRIP_CHECK',name,bool(value),flush=True)
    if not value:print('CHANGED_CAPTURE_PARTS',r.get('op_gi_changed'),flush=True)
    assert value,name
valid=lookdev.validate_capture(s,r)
if not valid:print('CHANGED_CAPTURE_PARTS',r.get('op_gi_changed'),flush=True)
check('saved capture initially valid',valid)
emitter=next(o for o in r.children if o.get('op_role')=='BIOME_INSTANCES' and len(o.data.vertices))
positions=array.array('f',[0])*(len(emitter.data.vertices)*3)
emitter.data.vertices.foreach_get('co',positions)
vertex=emitter.data.vertices[0];vertex.co.x+=.00001
check('edited placement invalidates',not lookdev.validate_capture(s,r))
emitter.data.vertices.foreach_set('co',positions)
check('restored placement recovers',lookdev.validate_capture(s,r))
sun=next(o for o in r.children if o.get('op_biome_light')=='Sun');old=sun.data.energy;sun.data.energy+=.1
check('edited sun invalidates',not lookdev.validate_capture(s,r))
sun.data.energy=old
check('restored sun recovers',lookdev.validate_capture(s,r))
def source_key(socket):
    return (socket.links[0].from_node.name,socket.links[0].from_socket.name) if socket.is_linked else float(socket.default_value)
alphas={}
for mat in bpy.data.materials:
    if mat.get('op_air_owner')!=r.name:continue
    wrapper=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.get('op_air_owner')==r.name)
    source=wrapper.inputs['Surface'].links[0].from_node
    if source.type=='BSDF_PRINCIPLED':alphas[mat.name]=(source.name,source_key(wrapper.inputs['Alpha']))
check('alpha-bearing source materials found',bool(alphas))
r['lod_enabled']=False
lookdev.disable(s,r)
check('restore recovers legacy fill light',all(o.data.energy>0 for o in r.children if o.get('op_biome_light') in {'Sky fill','Horizon fill'}))
check('restore removes air wrappers',all(not mat.get('op_air_owner') for mat in bpy.data.materials if mat.name in alphas))
check('restore keeps source alpha',all(source_key(bpy.data.materials[name].node_tree.nodes[node].inputs['Alpha'])==value for name,(node,value) in alphas.items()))
lookdev.enable(s,r)
check('frozen-detail upgrade removes legacy fills',all(o.data.energy==0 for o in r.children if o.get('op_biome_light') in {'Sky fill','Horizon fill'}))
check('upgrade wraps source once',all(sum(n.type=='GROUP' and n.node_tree and n.node_tree.get('op_air_owner')==r.name for n in bpy.data.materials[name].node_tree.nodes)==1 for name in alphas))
check('upgrade keeps alpha coverage',all(source_key(next(n for n in bpy.data.materials[name].node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.get('op_air_owner')==r.name).inputs['Alpha'])==value for name,(node,value) in alphas.items()))
icons=bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items
check('lighting bake UI icon exists','LIGHTPROBE_VOLUME' in icons.keys())
(OUT/'look_roundtrip_validation.json').write_text(json.dumps(checks,indent=2))
print('LOOK_ROUNDTRIP_COMPLETE',flush=True)
