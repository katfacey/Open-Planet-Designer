"""Isolate clear-air altitude continuity with cached geometry and no clouds."""
import json,sys,time
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,lookdev
OUT=ROOT/'output/next-realism'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'daylight_grassland.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
lod.unregister()
detail=s.camera;r.op_lod.camera=detail
cp,_=lod.logical_camera(r,detail.evaluated_get(bpy.context.evaluated_depsgraph_get()))
up=cp.normalized()
east=Vector((0,0,1)).cross(up).normalized()
tangent=up.cross(east).normalized()
view=detail.copy();view.data=detail.data.copy();view.name='Development · Clear-air altitude camera'
r.users_collection[0].objects.link(view);view.animation_data_clear();s.camera=view
r['lod_enabled']=False
for ob in r.children:
    if ob.get('op_role') in {'CLOUDS','DAYLIGHT_PROBE'}:ob.hide_render=True
    elif ob.get('op_role')=='ATMOSPHERE':ob.hide_render=False
s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100
s.view_settings.exposure=1.5;s.eevee.taa_render_samples=64;s.cycles.samples=64
s.cycles.use_denoising=True;s.cycles.device='GPU'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
metres=r['radius']*s.unit_settings.scale_length
view.data.clip_end=r['radius']*4
view.data.clip_start=view.data.clip_end*1e-6
view.rotation_euler=(r.matrix_local.to_quaternion() @ (-up*.12+tangent).to_track_quat('-Z','Y')).to_euler()
records=[]
for altitude in (10000,30000,80000,90000,99000,100000,101000,120000):
    view.location=r.matrix_local @ (up*(1.+altitude/metres))
    bpy.context.view_layer.update();lookdev.environment(s,r);lookdev.lighting(s,r)
    actual=r['op_camera_altitude_m']
    assert abs(actual-altitude)<2.,(actual,altitude)
    record={'altitude_m':altitude,'measured_m':actual,'sky_weight':r['op_daylight_sky_weight'],'renders':{}}
    for engine,name in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
        s.render.engine=engine;s.render.filepath=str(OUT/('air_'+str(altitude)+'_'+name+'.png'))
        start=time.perf_counter();bpy.ops.render.render(write_still=True)
        record['renders'][name]=time.perf_counter()-start
    records.append(record)
    print('AIR_CHECK',json.dumps(record),flush=True)
    (OUT/'clear_air_validation.json').write_text(json.dumps(records,indent=2))
print('AIR_VALIDATION_COMPLETE',flush=True)
