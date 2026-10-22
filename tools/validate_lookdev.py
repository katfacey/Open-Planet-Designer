"""Native Blender acceptance checks and fixed-exposure engine comparisons.

Run with Blender 5.2 --background --factory-startup --python-exit-code 1
--python tools/validate_lookdev.py -- --site Forest [--reload]
"""
import argparse,json,sys,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,lookdev

parser=argparse.ArgumentParser()
parser.add_argument('--site',default='Forest')
parser.add_argument('--reload',action='store_true')
parser.add_argument('--no-render',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/'output/next-realism';OUT.mkdir(exist_ok=True,parents=True)
review=OUT/('daylight_'+args.site.lower()+'.blend')
fixture=OUT/('fixture_'+args.site.lower()+'.blend')
source=review if args.reload else fixture if fixture.exists() else ROOT/'dist/Open-Planet-Designer-Beta-Demo.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
s.camera=bpy.data.objects['Entry Camera · '+args.site];r.op_lod.camera=s.camera
s.frame_set(240);r['lod_auto']=False
lod.unregister()
if bpy.app.timers.is_registered(lod._timer):bpy.app.timers.unregister(lod._timer)
s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100
s.view_settings.exposure=3.
s.eevee.taa_render_samples=128;s.eevee.shadow_pool_size='512'
s.cycles.samples=128;s.cycles.use_denoising=True;s.cycles.transparent_max_bounces=64
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU'
report={'site':args.site,'reload':args.reload,'exposure':s.view_settings.exposure,'checks':{},'renders':{}}
def check(name,value):
    report['checks'][name]=bool(value)
    print('LOOK_CHECK',name,bool(value),flush=True)
    if not value:raise AssertionError(name)
if not args.reload:
    start=time.perf_counter();lookdev.enable(s,r)
    report['upgrade_seconds']=time.perf_counter()-start
    print('LOOK_UPGRADE_SECONDS',report['upgrade_seconds'],flush=True)
    check('true terrain and instances retained',r.get('op_biome_triangles',0)>0 and r.get('op_lod_triangles',0)>0)
    surface=next(o for o in r.children if o.get('op_role')=='SURFACE')
    images=[n for n in surface.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.label.startswith('Substrate')]
    check('four color height roughness triplets',len(images)==12)
    check('ground data maps non-color',all(n.image.colorspace_settings.name=='Non-Color' for n in images if not n.label.endswith('color')))
    report['material_status']=r.get('op_air_material_status')
    report['material_skipped']=r.get('op_air_material_skipped')
    start=time.perf_counter();lookdev.bake(s,r)
    report['bake_seconds']=time.perf_counter()-start
check('current capture valid',lookdev.validate_capture(s,r))
probe=lookdev.probe_for(r)
check('probe intensity remains one',probe.data.intensity==1.)
check('unshadowed legacy fills removed',all(o.data.energy==0 for o in r.children if o.get('op_biome_light') in {'Sky fill','Horizon fill'}))
signature=probe.get('op_shot_signature')
if not args.reload:
    lod.update(s,r,True)
    check('identical forced detail rebuild keeps capture',lookdev.validate_capture(s,r))
old=r['look_moisture'];r['look_moisture']=min(1.,old+.2)
check('changed material disables capture',not lookdev.validate_capture(s,r) and probe.hide_render)
r['look_moisture']=old
check('restored material recovers capture',lookdev.validate_capture(s,r))
cam=s.camera;old_lens=cam.data.lens;cam.data.lens=old_lens+1
check('changed lens disables capture',not lookdev.validate_capture(s,r))
cam.data.lens=old_lens
check('restored lens recovers capture',lookdev.validate_capture(s,r))
check('signature persisted',probe.get('op_shot_signature')==signature)
if not args.no_render:
    for engine,name in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
        s.render.engine=engine;s.render.filepath=str(OUT/('development_'+args.site.lower()+'_'+name+'.png'))
        start=time.perf_counter();bpy.ops.render.render(write_still=True)
        report['renders'][name]=time.perf_counter()-start
        print('LOOK_RENDER',name,report['renders'][name],flush=True)
if not args.reload:
    s.render.engine='BLENDER_EEVEE'
    bpy.ops.wm.save_as_mainfile(filepath=str(review),compress=True)
(OUT/('validation_'+args.site.lower()+('_reload' if args.reload else '')+'.json')).write_text(json.dumps(report,indent=2))
print('LOOK_VALIDATION_COMPLETE',flush=True)
