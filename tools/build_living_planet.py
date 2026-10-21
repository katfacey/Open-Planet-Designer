"""Build five camera sites on one continuous climate-driven world and render pairs."""
import sys,json,math,time
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import generator,lod,biome
OUT=ROOT/'output/planets/living';OUT.mkdir(exist_ok=True)
base=bpy.data.scenes.new('OP · Living Planet');bpy.context.window.scene=base;generator.configure(base,960,540)
generator.camera(base);r=generator.create_planet(base,'TERRA',128,name='Terra · Living Biomes')
for k,v in dict(radius=10000.,biome_enabled=True,ice=.94,city_lights=0.,cloud_coverage=.18,atmosphere=.22,
    atmosphere_height=.0157,cloud_height=.0016,cloud_depth=.0005,haze=.025,lod_enabled=True,lod_budget=500000,lod_pixels=2.,
    lod_near=.00003,lod_far=.02,lod_max_depth=24,lod_micro_normal=.04,biome_budget=3000000,biome_instances=16000).items():r[k]=v
r.op_lod.camera=None;r.update_tag();bpy.context.view_layer.update()
base.unit_settings.scale_length=637.1
base.unit_settings.system='METRIC'
r.driver_add('["biome_time"]').driver.expression='frame/24'
generator.upgrade_entry(base,r,refresh=False)
directions=[]
for i in range(14000):
    z=1.-2.*(i+.5)/14000.;a=i*math.pi*(3.-math.sqrt(5.));d=Vector((math.sqrt(1.-z*z)*math.cos(a),math.sqrt(1.-z*z)*math.sin(a),z))
    if d.y<-.3 and abs(z)<.7:directions.append(tuple(d))
points,weights=biome.sample(base,r,directions)
targets={}
for name,mask in (('Grassland','grass'),('Forest','forest'),('Alpine','mountain'),('Desert','desert')):
    eligible=[i for i,d in enumerate(directions) if weights['land'][i]>.995 and Vector(d).dot(Vector((-.507,-.725,.469)))>.25]
    if name in ('Alpine','Desert'):eligible=[i for i in eligible if weights['continent'][i]>r['sea_level']+.06]
    # Prioritize a strong unambiguous biome over latitude or camera-specific tricks.
    if name=='Alpine':i=min((i for i in eligible if weights[mask][i]>.85),key=lambda i:points[i].length)
    elif name=='Desert':i=max(eligible,key=lambda i:weights[mask][i]-.3*abs(weights['canyon'][i]-.95))
    else:i=max(eligible,key=lambda i:weights[mask][i])
    targets[name]=(Vector(directions[i]),{k:round(v[i],4) for k,v in weights.items()})
i=min((i for i,d in enumerate(directions) if Vector(d).dot(Vector((-.507,-.725,.469)))>.5),key=lambda i:weights['land'][i]+abs(directions[i][2]-.35)*.01)
targets['Ocean']=(Vector(directions[i]),{k:round(v[i],4) for k,v in weights.items()})
def dem_site(direction,uv):
    longitude=math.atan2(direction.y,direction.x);colat=math.acos(direction.z)
    u=(longitude/math.tau+.5)*384.;v=colat/math.pi*192.
    longitude=((math.floor(u)+uv[0])/384.-.5)*math.tau;colat=(math.floor(v)+uv[1])/192.*math.pi
    return Vector((math.sin(colat)*math.cos(longitude),math.sin(colat)*math.sin(longitude),math.cos(colat)))
# Compose the two elevation-data views within their existing climate cells.
targets['Alpine']=(dem_site(targets['Alpine'][0],(.24,.70)),targets['Alpine'][1])
targets['Desert']=(dem_site(targets['Desert'][0],(.3583984375,.2783203125)),targets['Desert'][1])
_,actual_weights=biome.sample(base,r,[tuple(v[0]) for v in targets.values()])
for i,name in enumerate(targets):targets[name]=(targets[name][0],{k:round(v[i],4) for k,v in actual_weights.items()})
print('BIOME_TARGETS',json.dumps({k:v[1] for k,v in targets.items()}),flush=True)
scenes={};cameras={};clearances={'Grassland':.00000028,'Forest':.00000055,'Ocean':.0000018,'Alpine':.00025,'Desert':.000003}
for name in ('Grassland','Forest','Ocean','Alpine','Desert'):
    s=base
    cam=s.camera if name=='Grassland' else generator.camera(s)
    cam.name='Entry Camera · '+name;cam.data.type='PERSP';cam.data.lens=32.;cam['op_entry_camera']=True
    for ob in r.children:
        for mod in ob.modifiers:
            if mod.type=='NODES' and mod.node_group:
                camera_node=mod.node_group.nodes.get('LOD Camera')
                if camera_node:camera_node.inputs['Object'].default_value=cam
    s.render.use_lock_interface=True;s.cycles.transparent_max_bounces=64
    direction,mask=targets[name];tangent=(Vector((0,0,1))-direction*direction.z).normalized()
    h=biome.sample(s,r,[tuple(direction)])[0][0].length;path=[];looktarget=None
    if name in ('Alpine','Desert'):
        east=direction.cross(tangent).normalized();neighbours=[]
        for reach in (.0004,.0008,.0015):
            for axis in (tangent,-tangent,east,-east):neighbours.append(tuple((direction+axis*reach).normalized()))
        np,nw=biome.sample(s,r,neighbours);j=max(range(len(np)),key=lambda j:np[j].length)
        looktarget=np[j]*r['radius']
        if name=='Alpine':
            target=dem_site(direction,(.24,.85));looktarget=biome.sample(s,r,[tuple(target)])[0][0]*r['radius']
        elif name=='Desert':
            target=dem_site(direction,(.3046875,.35546875));looktarget=biome.sample(s,r,[tuple(target)])[0][0]*r['radius']
    for frame,alt in ((1,3.),(90,.03),(150,.0007),(200,clearances[name]*8),(240,clearances[name])):
        cam.location=direction*r['radius']*(h+alt)
        # Camera height follows the same animated wave/terrain evaluator.
        for _ in range(2):
            bpy.context.view_layer.update();h=biome.sample(s,r,[tuple(direction)])[0][0].length
            cam.location=direction*r['radius']*(h+alt)
        blend=1.-min(1.,alt/.03);down=.22 if name in ('Alpine','Desert') else .12
        ray=(-direction*(1.-blend*(1.-down))+tangent*blend).normalized()
        if looktarget is not None and alt<.0008:ray=(looktarget-cam.location).normalized()
        up=direction-ray*direction.dot(ray)
        if up.length<.001:up=tangent
        right=ray.cross(up).normalized();up=right.cross(ray).normalized()
        rotation=Matrix((right,up,-ray)).transposed().to_quaternion().to_euler()
        path.append((frame,cam.location.copy(),rotation))
    for f,loc,rot in path:
        cam.location=loc;cam.rotation_euler=rot;cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
    for layer in cam.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for key in fc.keyframe_points:key.interpolation='LINEAR'
    cam['op_biome_site']=name;cam['op_site_direction']=tuple(direction);scenes[name]=s;cameras[name]=cam

# One world/depsgraph with five cameras; all views share the same geography.
biome.setup_world(base,r)

prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX' and '5090' in d.name
selected=sys.argv[sys.argv.index('--')+1].split(',') if '--' in sys.argv else list(scenes)
report={}
for name in selected:
    s=base;s.camera=cameras[name];s.frame_set(240);bpy.context.view_layer.update();start=time.perf_counter();lod.update(s,r,True)
    surface=next(o for o in r.children if o.get('op_role')=='SURFACE');dg=bpy.context.evaluated_depsgraph_get();mesh=surface.evaluated_get(dg).data
    origin=Vector(tuple(r.get('op_anchor_'+a,0.) for a in 'xyz'))
    h=[(v.co+origin).length for v in mesh.vertices];cp=r.matrix_world.inverted()@s.camera.matrix_world.translation
    stats={'terrain_triangles':r['op_lod_triangles'],'scatter_triangles':r.get('op_biome_triangles'),
        'instances':r.get('op_biome_instances'),'update_seconds':time.perf_counter()-start,
        'terrain_radial_range':max(h)-min(h),'site':targets[name][1],
        'camera_clearance_radius':cp.length-biome.sample(s,r,[tuple(cp.normalized())])[0][0].length}
    for engine,label in (('BLENDER_EEVEE','eevee'),('CYCLES','cycles')):
        s.render.engine=engine;s.cycles.device='GPU';s.cycles.samples=128;s.cycles.use_denoising=True
        s.render.filepath=str(OUT/(name.lower()+'_'+label+'.png'));t=time.perf_counter();bpy.ops.render.render(write_still=True)
        stats[label+'_seconds']=time.perf_counter()-t
    report[name]=stats;print('LIVING_FRAME',name,json.dumps(stats),flush=True)
base.camera=cameras['Forest'];base.oplab.entry_camera=cameras['Forest'];base.frame_set(240)
base.render.engine='BLENDER_EEVEE';base.render.filepath=str(OUT/'living_render.png');lod.update(base,r,True)
surface=next(o for o in r.children if o.get('op_role')=='SURFACE')
for o in bpy.context.selected_objects:o.select_set(False)
surface.select_set(True);bpy.context.view_layer.objects.active=surface
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='RENDERED'
            area.spaces.active.overlay.show_overlays=False;area.spaces.active.show_region_ui=True
text=bpy.data.texts.new('START HERE · Living Planet')
text.write('OPEN PLANET DESIGNER 1.2\nFive entry cameras share ONE world: choose Shot camera in N > Open Planet, scrub 1-240.\nLiving Surface: physical terrain, tree/grass/rock instances, animated geometric waves.\nTerrain and scatter have separate hard triangle budgets.\nCC0 source assets: Poly Haven. Full sources/license and LOD counts are in the addon assets folder.\n')
(OUT/'living_verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Open_Planet_Living_Biomes.blend'),compress=True)
print('LIVING_DEMO_COMPLETE',flush=True)
