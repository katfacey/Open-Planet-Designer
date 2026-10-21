"""Upgrade a copy of the preserved live planet and render review views."""
import sys,json,time,math
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab;open_planet_lab.register()
from open_planet_lab import biome,generator,lod,terrain_regions,nodes
OUT=ROOT/'output/planets/realism';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Before_Realism_Priorities.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
r['biome_realism']=True;r['biome_tree_distance']=.00018;r['biome_budget']=5000000;r['biome_instances']=90000
r['biome_density']=.88;r['lod_budget']=500000;r['lod_pixels']=2.;r['biome_tree_height']=.0000035
biome.ensure(r);generator.upgrade_entry(s,r,refresh=False);terrain_regions.configure(s,r);generator.upgrade_entry(s,r,refresh=False)
s.render.resolution_x=1280;s.render.resolution_y=720;s.render.resolution_percentage=100
s.render.use_lock_interface=True;s.cycles.transparent_max_bounces=64
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'

def pose(cam,direction,altitude_m,target=None):
    bpy.context.view_layer.update();p,_=biome.sample(s,r,[tuple(direction)])
    height=p[0].length;cam.location=direction*r['radius']*(height+altitude_m/6371000.)
    forward=(Vector(target)-cam.location).normalized() if target is not None else (Vector((0,0,1))-direction*direction.z-direction*.09).normalized()
    up=direction-forward*forward.dot(direction)
    right=forward.cross(up).normalized();up=right.cross(forward).normalized()
    cam.rotation_euler=Matrix((right,up,-forward)).transposed().to_euler()

for site in ('Forest','Grassland'):
    cam=bpy.data.objects['Entry Camera · '+site];s.camera=cam;s.frame_set(240)
    direction=Vector(cam['op_site_direction']).normalized();pose(cam,direction,2.2 if site=='Forest' else 1.7)
    cam.keyframe_insert('location',frame=240);cam.keyframe_insert('rotation_euler',frame=240)

for site,name,uv,lookuv,alt in (('Alpine','rainier',(.56,.14),(.49,.51),120.),('Desert','canyon',(.52,.47),(.32,.60),120.)):
    region=next(x for x in terrain_regions.regions(r) if x['name']==name);meta=terrain_regions.metadata(name)
    def direction_at(pair):return (Vector(region['center'])+Vector(region['east'])*(pair[0]-.5)*meta['width_m']/6371000.+Vector(region['north'])*(pair[1]-.5)*meta['width_m']/6371000.).normalized()
    direction=direction_at(uv);targetdir=direction_at(lookuv);s.camera=bpy.data.objects['Entry Camera · '+site];s.frame_set(240)
    target=biome.sample(s,r,[tuple(targetdir)])[0][0]*r['radius']
    if site=='Desert':target=targetdir*r['radius']*(biome.sample(s,r,[tuple(direction)])[0][0].length+50./6371000.)
    pose(s.camera,direction,alt,target)
    s.camera.keyframe_insert('location',frame=240);s.camera.keyframe_insert('rotation_euler',frame=240)
    s.camera['op_review_direction']=tuple(direction)

views=sys.argv[sys.argv.index('--views')+1].split(',') if '--views' in sys.argv else ('Forest','Grassland','Alpine','Desert')
report={}
for site in views:
    s.camera=bpy.data.objects['Entry Camera · '+site];s.frame_set(240);bpy.context.view_layer.update();start=time.perf_counter();lod.update(s,r,True)
    record=dict(terrain_triangles=r['op_lod_triangles'],scatter_triangles=r['op_biome_triangles'],instances=r['op_biome_instances'],update_seconds=time.perf_counter()-start,ecology=json.loads(r.get('op_ecology_counts','{}')),reach=json.loads(r.get('op_ecology_reach','{}')),status=r['op_lod_status'])
    for engine,label in (('BLENDER_EEVEE','eevee'),('CYCLES','cycles')):
        s.render.engine=engine;s.cycles.device='GPU';s.cycles.samples=128;s.cycles.use_denoising=True
        s.render.filepath=str(OUT/(site.lower()+'_'+label+'.png'));start=time.perf_counter();bpy.ops.render.render(write_still=True);record[label+'_seconds']=time.perf_counter()-start
    report[site]=record;print('REALISM_REVIEW',site,json.dumps(record),flush=True)
s.camera=bpy.data.objects['Entry Camera · Forest'];s.oplab.entry_camera=s.camera;s.frame_set(240);s.render.engine='BLENDER_EEVEE';lod.update(s,r,True)
r['op_realism_revision']='1.3.0 · first three proposal priorities'
nodes.refresh_loaded_controls(r);bpy.context.view_layer.update()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='RENDERED';area.spaces.active.overlay.show_overlays=False
(OUT/'realism_review.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Open_Planet_Realism_Priorities.blend'),compress=True)
print('REALISM_REVIEW_COMPLETE',flush=True)
