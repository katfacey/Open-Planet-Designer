# SPDX-License-Identifier: GPL-3.0-or-later
"""Render each frozen variant in a fresh Cycles-only process, without baking."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import foliage,lod
from open_planet_lab.nodes import refresh_loaded_controls
parser=argparse.ArgumentParser();parser.add_argument('--site',default='Forest')
parser.add_argument('--variant',choices=('before','after'),default='after')
parser.add_argument('--device',choices=('CPU','GPU'),default='GPU')
parser.add_argument('--reuse',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/'output/foliage-parity';name=args.site.lower()
path=OUT/('foliage_'+name+('_before' if args.variant=='before' else '')+'.blend')
bpy.ops.wm.open_mainfile(filepath=str(path));s=bpy.context.scene
r=next(o for o in s.objects if o.get('op_root'));lod.unregister();refresh_loaded_controls(r)
s.frame_set(s.frame_current);bpy.context.view_layer.update()
if args.device=='GPU':
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device=args.device;s.cycles.denoising_use_gpu=False
stem=name+'_'+args.variant+'_cycles';s.render.engine='CYCLES';s.render.filepath=str(OUT/(stem+'.png'))
if args.reuse and (OUT/(stem+'.exr')).exists() and (OUT/(stem+'.png')).exists():
    seconds='Reused completed 128-sample CPU render'
    used_device='CPU (reused)'
else:
    start=time.perf_counter();bpy.ops.render.render(write_still=True);seconds=time.perf_counter()-start
    s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_depth='32'
    bpy.data.images['Render Result'].save_render(str(OUT/(stem+'.exr')),scene=s)
    used_device=args.device
def read(path):
    image=bpy.data.images.load(str(path),check_existing=False);data=foliage.pixels(image)[:,:,:3].copy();bpy.data.images.remove(image);return data
a,b=[read(OUT/(name+'_'+args.variant+'_'+engine+'.exr')) for engine in ('eevee','cycles')]
error=np.abs(a-b);report=json.loads((OUT/'validation.json').read_text());record=report[args.site]
record['renders'][stem]=seconds;record['cycles_device']=args.device
record.setdefault('cycles_devices',{})[args.variant]=used_device
record['comparisons'][args.variant]={'linear_rgb_mae':float(error.mean()),'linear_rgb_p95':float(np.percentile(error,95)),
    'linear_normalized_mae':float(error.mean()/max((a.mean()+b.mean())*.5,1e-8)),
    'linear_eevee_mean':float(a.mean()),'linear_cycles_mean':float(b.mean())}
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
print('FOLIAGE_CYCLES_COMPLETE',args.site,args.variant,seconds,flush=True)
