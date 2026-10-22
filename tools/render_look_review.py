"""Readable static-shot reviews; identical exposure within each engine pair."""
import argparse,json,sys,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,lookdev
parser=argparse.ArgumentParser()
parser.add_argument('--sites',default='Forest,Grassland,Alpine,Desert')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/'output/next-realism';report={}
for site in args.sites.split(','):
    bpy.ops.wm.open_mainfile(filepath=str(OUT/('daylight_'+site.lower()+'.blend')))
    s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
    s.frame_set(s.frame_current);lod.unregister();r['lod_enabled']=False;r['lod_auto']=False
    s.view_settings.exposure=3. if site=='Forest' else 0.
    s.cycles.device='GPU'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    start=time.perf_counter();lookdev.bake(s,r)
    record={'exposure':s.view_settings.exposure,'frozen_geometry':True,'bake_seconds':time.perf_counter()-start,'renders':{}}
    for engine,name in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
        s.render.engine=engine;s.render.filepath=str(OUT/('review_'+site.lower()+'_'+name+'.png'))
        start=time.perf_counter();bpy.ops.render.render(write_still=True)
        record['renders'][name]=time.perf_counter()-start
    if site=='Forest':
        s.render.engine='BLENDER_EEVEE'
        assert lookdev.validate_capture(s,r),'Static review changed after baking'
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Open-Planet-Designer-1.4-Development-Review.blend'),compress=True)
    report[site]=record
    (OUT/'readable_review.json').write_text(json.dumps(report,indent=2))
    print('READABLE_REVIEW',site,json.dumps(record),flush=True)
print('READABLE_REVIEW_COMPLETE',flush=True)
