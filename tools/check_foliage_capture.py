# SPDX-License-Identifier: GPL-3.0-or-later
"""Reopen a saved foliage capture and verify stale-cache/restore behavior."""
import argparse,array,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import foliage,lod,lookdev
from open_planet_lab.nodes import refresh_loaded_controls
parser=argparse.ArgumentParser();parser.add_argument('--file',default='foliage_forest.blend')
parser.add_argument('--rebake',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/'output/foliage-parity'
bpy.ops.wm.open_mainfile(filepath=str(OUT/args.file))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'));lod.unregister()
refresh_loaded_controls(r);s.frame_set(s.frame_current);bpy.context.view_layer.update()
if args.rebake:
    lookdev.bake(s,r)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/args.file),compress=True)
checks={}
def check(name,value):
    checks[name]=bool(value);print('FOLIAGE_CACHE_CHECK',name,bool(value),flush=True)
    if not value:print('CHANGED_CAPTURE_PARTS',r.get('op_gi_changed'),flush=True)
    assert value,name
check('saved capture initially valid',lookdev.validate_capture(s,r))
ob=next(o for o in foliage.sources(r) if o.get('op_asset_kind')=='TREE')
mat=ob.data.materials[0];fix=mat.node_tree.nodes[foliage.FIX]
old=tuple(fix.inputs[1].default_value);fix.inputs[1].default_value=(1,1,-.8)
check('edited normal conversion invalidates',not lookdev.validate_capture(s,r))
fix.inputs[1].default_value=old
check('restored normal conversion recovers',lookdev.validate_capture(s,r))
old=fix.operation;fix.operation='MULTIPLY'
check('edited node operation invalidates',not lookdev.validate_capture(s,r))
fix.operation=old
check('restored node operation recovers',lookdev.validate_capture(s,r))
old=mat.use_transparent_shadow;mat.use_transparent_shadow=not old
check('edited transparent shadow setting invalidates',not lookdev.validate_capture(s,r))
mat.use_transparent_shadow=old
check('restored transparent shadow setting recovers',lookdev.validate_capture(s,r))
probe=lookdev.probe_for(r);old=probe.data.normal_bias;probe.data.normal_bias=old+.1
check('edited probe bias invalidates',not lookdev.validate_capture(s,r))
probe.data.normal_bias=old
check('restored probe bias recovers',lookdev.validate_capture(s,r))
old=probe.location.copy();probe.location.x+=1e-5;bpy.context.view_layer.update()
check('edited probe placement invalidates',not lookdev.validate_capture(s,r))
probe.location=old;bpy.context.view_layer.update()
check('restored probe placement recovers',lookdev.validate_capture(s,r))
uv=ob.data.uv_layers.active.data[0]
saved_uvs=array.array('f',[0])*(len(ob.data.loops)*2)
ob.data.uv_layers.active.data.foreach_get('uv',saved_uvs)
uv.uv.x+=.01
check('edited crown UV invalidates',not lookdev.validate_capture(s,r))
ob.data.uv_layers.active.data.foreach_set('uv',saved_uvs)
check('restored crown UV recovers',lookdev.validate_capture(s,r))
with foliage.capture_sources(r):pass
check('temporary capture support leaves signature unchanged',lookdev.validate_capture(s,r))
foliage.restore(r)
check('foliage restore removes normal fixes',all(not m.node_tree.nodes.get(foliage.FIX) for o in foliage.sources(r) for m in o.data.materials))
check('foliage restore invalidates repaired capture',not lookdev.validate_capture(s,r))
foliage.enable(s,r)
check('repeated repair recovers exact signature',lookdev.validate_capture(s,r))
check('no temporary geometry persists',not any('temporary capture support' in m.name for m in bpy.data.meshes))
(OUT/'capture_checks.json').write_text(json.dumps(checks,indent=2))
print('FOLIAGE_CAPTURE_CHECKS_COMPLETE',flush=True)
