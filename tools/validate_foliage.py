# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen forest/meadow pairs and native foliage/capture restoration checks."""
import argparse,array,hashlib,json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import foliage,lod,lookdev
from open_planet_lab.nodes import refresh_loaded_controls
parser=argparse.ArgumentParser();parser.add_argument('--sites',default='Forest,Grassland')
parser.add_argument('--reload',action='store_true')
parser.add_argument('--cycles-device',choices=('CPU','GPU'),default='GPU')
parser.add_argument('--resume',action='store_true')
parser.add_argument('--prepare-only',action='store_true',help='Save both frozen variants; render Cycles in a fresh process')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/'output/foliage-parity';OUT.mkdir(exist_ok=True,parents=True)
report={}


def placements(root):
    digest=hashlib.sha256()
    for ob in sorted(root.children,key=lambda x:x.name):
        if ob.get('op_role')!='BIOME_INSTANCES':continue
        digest.update(ob.name.encode())
        for coll,prop,count,kind in [(ob.data.vertices,'co',3,'f')]:
            data=array.array(kind,[0])*(len(coll)*count);coll.foreach_get(prop,data);digest.update(data.tobytes())
        for name in ('id','op_rotation','op_scale'):
            attr=ob.data.attributes.get(name)
            if not attr:continue
            vector=attr.data_type=='FLOAT_VECTOR';data=array.array('f' if vector else 'i',[0])*(len(attr.data)*(3 if vector else 1))
            attr.data.foreach_get('vector' if vector else 'value',data);digest.update(data.tobytes())
    return digest.hexdigest()


for site in args.sites.split(','):
    path=OUT/('foliage_'+site.lower()+'.blend') if args.reload else ROOT/'output/next-realism'/('daylight_'+site.lower()+'.blend')
    bpy.ops.wm.open_mainfile(filepath=str(path));s=bpy.context.scene
    r=next(o for o in s.objects if o.get('op_root'));lod.unregister()
    refresh_loaded_controls(r);lookdev.ensure(s,r)
    s.frame_set(s.frame_current);r['lod_enabled']=False;r['lod_auto']=False
    s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100
    s.view_settings.exposure=3.;s.eevee.taa_render_samples=128;s.cycles.samples=128
    s.cycles.seed=17;s.cycles.use_denoising=True;s.cycles.transparent_max_bounces=64
    if args.cycles_device=='GPU':
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
        for device in prefs.devices:device.use=device.type=='OPTIX'
    s.cycles.device=args.cycles_device
    record={'checks':{},'exposure_ev':3.,'resolution':[960,540],'samples':128,
            'cycles_denoising':True,'cycles_device':args.cycles_device,'transparent_bounces':64,'comparisons':{},'renders':{}}
    report[site]=record
    def check(name,value):
        record['checks'][name]=bool(value);print('FOLIAGE_CHECK',site,name,bool(value),flush=True)
        if not value:raise AssertionError(name)
    if args.reload:
        check('saved capture valid',lookdev.validate_capture(s,r))
        check('saved corrected crown shaders',all(m.node_tree.nodes.get(foliage.FIX) for o in foliage.sources(r) for m in o.data.materials
                                               if foliage.pixels(foliage.atlas(m,'color'))[:,:,3].max()>.5))
        check('no temporary meshes saved',not any('temporary capture support' in m.name for m in bpy.data.meshes))
        (OUT/('reload_'+site.lower()+'.json')).write_text(json.dumps(record,indent=2));continue
    original_sources={ob.name:ob.data for ob in foliage.sources(r)}
    initial_placements=placements(r);initial_counts=r.get('op_ecology_counts');initial_budget=r.get('op_biome_triangles')
    linear={}
    for variant in ('before','after'):
        if variant=='after':
            foliage.enable(s,r);foliage.enable(s,r)
            check('repair idempotent',all(sum(n.name==foliage.FIX for n in m.node_tree.nodes)==1
                                         for o in foliage.sources(r) for m in o.data.materials
                                         if foliage.pixels(foliage.atlas(m,'color'))[:,:,3].max()>.5))
            mesh_count=len(bpy.data.meshes);curve_count=len(bpy.data.curves);object_count=len(bpy.data.objects)
            try:
                with foliage.capture_sources(r) as stats:
                    check('all seven crowns have capture support',len(stats)==7 and all(x['support_triangles']>6 for x in stats))
                    raise RuntimeError('Injected capture failure')
            except RuntimeError as error:
                if str(error)!='Injected capture failure':raise
            check('failure restores original source data',all(bpy.data.objects[name].data==mesh for name,mesh in original_sources.items()))
            check('failure leaves no temporary data',(len(bpy.data.meshes),len(bpy.data.curves),len(bpy.data.objects))==(mesh_count,curve_count,object_count))
        start=time.perf_counter();lookdev.bake(s,r)
        record[variant+'_bake_seconds']=time.perf_counter()-start
        check(variant+' capture valid',lookdev.validate_capture(s,r))
        pair={}
        for engine,label in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
            if args.prepare_only and label=='cycles':continue
            stem='_'.join((site.lower(),variant,label));s.render.engine=engine;s.render.filepath=str(OUT/(stem+'.png'))
            path=OUT/(stem+'.exr')
            if not(args.resume and path.exists() and Path(s.render.filepath).exists()):
                start=time.perf_counter();bpy.ops.render.render(write_still=True)
                record['renders'][stem]=time.perf_counter()-start
                s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_depth='32'
                bpy.data.images['Render Result'].save_render(str(path),scene=s)
            else:record['renders'][stem]='Reused completed matching render'
            image=bpy.data.images.load(str(path),check_existing=False);data=foliage.pixels(image)[:,:,:3].copy();bpy.data.images.remove(image)
            pair[label]=data
            s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8'
        if variant=='before' and args.prepare_only:
            bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('foliage_'+site.lower()+'_before.blend')),compress=True)
        if 'cycles' not in pair:continue
        a,b=pair['eevee'],pair['cycles'];error=np.abs(a-b)
        # Symmetric normalized linear error, sensitive to lighting rather than display curve.
        record['comparisons'][variant]={'linear_rgb_mae':float(error.mean()),
            'linear_rgb_p95':float(np.percentile(error,95)),
            'linear_normalized_mae':float(error.mean()/max((a.mean()+b.mean())*.5,1e-8)),
            'linear_eevee_mean':float(a.mean()),'linear_cycles_mean':float(b.mean())}
    check('placements IDs rotations and sizes unchanged',placements(r)==initial_placements)
    check('instance counts unchanged',r.get('op_ecology_counts')==initial_counts)
    check('runtime triangle budget unchanged',r.get('op_biome_triangles')==initial_budget)
    check('all runtime sources restored',all(bpy.data.objects[name].data==mesh for name,mesh in original_sources.items()))
    check('render sources still six triangles',all(len(o.data.polygons)==3 for o in foliage.sources(r)))
    check('probe intensity one',lookdev.probe_for(r).data.intensity==1.)
    clearance=r['look_probe_clearance'];r['look_probe_clearance']=clearance+.1
    check('changed clearance invalidates capture',not lookdev.validate_capture(s,r))
    r['look_probe_clearance']=clearance
    check('restored clearance recovers capture',lookdev.validate_capture(s,r))
    record['normal_diagnostics']=json.loads(r.get('op_foliage_diagnostics','[]'))
    record['capture_support']=json.loads(r.get('op_foliage_capture_stats','[]'))
    record['runtime_triangles']=initial_budget;record['counts']=json.loads(initial_counts)
    record['placement_hash']=initial_placements
    s.render.engine='BLENDER_EEVEE'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('foliage_'+site.lower()+'.blend')),compress=True)
    (OUT/'validation.json').write_text(json.dumps(report,indent=2))
    print('FOLIAGE_SITE_COMPLETE',site,json.dumps(record['comparisons']),flush=True)
print('FOLIAGE_VALIDATION_COMPLETE',flush=True)
