# SPDX-License-Identifier: GPL-3.0-or-later
"""Controlled foliage transport/LOD tests, independent of planet haze and LOD.

blender --background --factory-startup --python-exit-code 1 --python
tools/foliage_benchmark.py -- --variant baseline --lights front,back,overcast
"""
import argparse,json,math,sys,time
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/foliage-parity';OUT.mkdir(exist_ok=True,parents=True)
parser=argparse.ArgumentParser()
parser.add_argument('--kind',default='TREE')
parser.add_argument('--levels',default='0,1,2')
parser.add_argument('--lights',default='front,back,overcast')
parser.add_argument('--variant',default='baseline',choices=['baseline','two_sided','no_normal','transparent_shadow','probe_only','no_fast_gi','no_probe','backface_zero','cutout','padded','cutout_padded','empty','bias','single_card','no_shadow','grid_above','normal_z','normal_cutout','capture_fix','capture_support'])
parser.add_argument('--samples',type=int,default=128)
parser.add_argument('--resolution',type=int,default=640)
parser.add_argument('--rotation',type=float,default=0.)
parser.add_argument('--tag',default='')
parser.add_argument('--cycles-device',choices=('CPU','GPU'),default='GPU')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.tag:
    OUT=OUT/args.tag;OUT.mkdir(exist_ok=True,parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
s.render.threads_mode='FIXED';s.render.threads=4
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1.
s.render.resolution_x=args.resolution;s.render.resolution_y=args.resolution;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.view_settings.view_transform='AgX';s.view_settings.look='None';s.view_settings.exposure=0.
s.eevee.taa_render_samples=args.samples;s.eevee.shadow_pool_size='512'
s.eevee.shadow_ray_count=16;s.eevee.shadow_step_count=32;s.eevee.use_raytracing=True
if args.variant in {'probe_only','no_fast_gi'}:s.eevee.use_fast_gi=False
if args.variant=='probe_only':s.eevee.use_raytracing=False
if args.variant=='backface_zero':s.eevee.ray_tracing_options.backface_radiance_scale=0.
s.cycles.samples=args.samples;s.cycles.use_denoising=False;s.cycles.seed=17;s.cycles.transparent_max_bounces=128
if args.cycles_device=='GPU':
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device=args.cycles_device
world=bpy.data.worlds.new('Uniform diffuse environment');world.use_nodes=True;s.world=world
world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
background=world.node_tree.nodes['Background'].inputs['Strength']
camera=bpy.data.objects.new('Fixed benchmark camera',bpy.data.cameras.new('Camera'))
s.collection.objects.link(camera);s.camera=camera;camera.location=(0,-55,13)
camera.rotation_euler=(Vector((0,0,11))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens=50;camera.data.clip_start=.05;camera.data.clip_end=500.
def gray_material():
    mat=bpy.data.materials.new('Neutral 18 percent reference');mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.18,.18,.18,1)
    bs.inputs['Roughness'].default_value=1.
    return mat
gray=gray_material()
bpy.ops.mesh.primitive_plane_add(size=200)
ground=bpy.context.object;ground.name='Diffuse ground';ground.data.materials.append(gray)
bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1.,location=(-10,-3,1))
sphere=bpy.context.object;sphere.name='Neutral lighting control';sphere.data.materials.append(gray)
for face in sphere.data.polygons:face.use_smooth=True
sun=bpy.data.objects.new('Benchmark sun',bpy.data.lights.new('Sun','SUN'));s.collection.objects.link(sun)
sun.data.color=(1,1,1);sun.data.angle=.0093;sun.data.use_shadow=True
sun.data.shadow_maximum_resolution=.01;sun.data.use_shadow_jitter=True
sun.data.shadow_buffer_clip_start=.001
if args.variant=='no_shadow':sun.data.use_shadow=False
levels=[int(x) for x in args.levels.split(',')]
names=['OP_'+args.kind+'_LOD'+str(i) for i in levels]
with bpy.data.libraries.load(str(ROOT/'open_planet_lab/assets/realism_library.blend'),link=False) as (src,dst):
    dst.objects=names
models={}
mat_report={}
for level,ob in zip(levels,dst.objects):
    assert ob is not None,names
    s.collection.objects.link(ob);ob.hide_render=True;ob.hide_set(False);ob.location=(0,0,0);ob.scale=(22.,)*3
    ob.rotation_euler.z=math.radians(args.rotation)
    if level==2 and args.variant=='single_card':
        import bmesh
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.delete(bm,geom=[face for face in bm.faces if face.material_index!=0],context='FACES')
        mesh=ob.data.copy();bm.to_mesh(mesh);bm.free();ob.data=mesh
    if level==2 and args.variant in {'cutout','cutout_padded','normal_cutout'}:
        sys.path.insert(0,str(ROOT/'tools'))
        from foliage_cutout_experiment import cutout
        cutout(ob)
    ob.data.calc_loop_triangles();models[level]=ob
    for mat in ob.data.materials:
        if not mat or mat.name in mat_report:continue
        data={key:getattr(mat,key,None) for key in ('surface_render_method','use_transparent_shadow','use_backface_culling','use_backface_culling_shadow','use_backface_culling_lightprobe_volume','thickness_mode','use_thickness_from_shadow')}
        data['normal_strengths']=[n.inputs['Strength'].default_value for n in mat.node_tree.nodes if n.type=='NORMAL_MAP']
        data['thickness']=[n.inputs['Thickness'].default_value for n in mat.node_tree.nodes if n.type=='OUTPUT_MATERIAL']
        mat_report[mat.name]=data
        if args.variant=='two_sided':mat.use_backface_culling_lightprobe_volume=False
        if args.variant=='transparent_shadow':mat.use_transparent_shadow=True
        if args.variant=='no_normal':
            for n in mat.node_tree.nodes:
                if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=0.
        if level==2 and args.variant in {'padded','cutout_padded'}:
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image and '_color' in node.image.filepath:
                    node.image=bpy.data.images.load(str(OUT/'dilated'/Path(node.image.filepath).name),check_existing=True)
        if level==2 and args.variant in {'normal_z','normal_cutout','capture_fix','capture_support'}:
            for node in list(mat.node_tree.nodes):
                if node.type!='NORMAL_MAP' or not node.inputs['Color'].is_linked:continue
                color=node.inputs['Color'].links[0].from_socket
                fix=mat.node_tree.nodes.new('ShaderNodeVectorMath');fix.operation='MULTIPLY_ADD'
                fix.inputs[1].default_value=(1,1,-1);fix.inputs[2].default_value=(0,0,1)
                mat.node_tree.links.new(color,fix.inputs[0]);mat.node_tree.links.new(fix.outputs['Vector'],node.inputs['Color'])
data=bpy.data.lightprobes.new('Finite tree capture','VOLUME')
probe=bpy.data.objects.new(data.name,data);s.collection.objects.link(probe)
probe.location=(0,0,12);probe.scale=(18,18,14)
data.resolution_x=data.resolution_y=24;data.resolution_z=16
data.bake_samples=256;data.surfel_density=48;data.capture_distance=40
data.capture_world=True;data.capture_indirect=True;data.capture_emission=False;data.clamp_indirect=0.;data.intensity=1.
if args.variant=='bias':data.normal_bias=1.
if args.variant in {'grid_above','capture_fix'}:probe.location.z=14.3
report={'kind':args.kind,'variant':args.variant,'samples':args.samples,'resolution':args.resolution,
    'rotation_degrees':args.rotation,'cycles_device':args.cycles_device,
    'exposure_ev':0.,'materials':mat_report,'renders':[]}
for level,ob in models.items():
    for other in models.values():other.hide_render=other!=ob or args.variant=='empty'
    for lighting in args.lights.split(','):
        direction=Vector((-.4,-.8 if lighting=='front' else .8,.45)).normalized()
        sun.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
        sun.data.energy=0. if lighting=='overcast' else 5.
        background.default_value=.4 if lighting=='overcast' else .08
        for selected in bpy.context.selected_objects:selected.select_set(False)
        probe.select_set(True);bpy.context.view_layer.objects.active=probe
        s.render.engine='BLENDER_EEVEE';bpy.context.view_layer.update()
        original=ob.data
        try:
            if level==2 and args.variant in {'capture_fix','capture_support'}:
                sys.path.insert(0,str(ROOT/'tools'))
                from foliage_cutout_experiment import cutout
                cutout(ob);bpy.context.view_layer.update()
            start=time.perf_counter();bpy.ops.object.lightprobe_cache_bake(subset='SELECTED')
        finally:
            ob.data=original;bpy.context.view_layer.update()
        bake_seconds=time.perf_counter()-start
        probe.hide_render=args.variant=='no_probe'
        for engine,label in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
            stem='_'.join((args.variant,args.kind.lower(),'lod'+str(level),lighting,label))
            s.render.engine=engine;s.render.filepath=str(OUT/(stem+'.png'))
            start=time.perf_counter();bpy.ops.render.render(write_still=True)
            seconds=time.perf_counter()-start
            s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_depth='32'
            bpy.data.images['Render Result'].save_render(str(OUT/(stem+'.exr')),scene=s)
            s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8'
            row={'level':level,'lighting':lighting,'engine':label,'triangles':len(ob.data.loop_triangles),'bake_seconds':bake_seconds,'render_seconds':seconds}
            report['renders'].append(row);print('FOLIAGE_RENDER',json.dumps(row),flush=True)
            (OUT/(args.variant+'_'+args.kind.lower()+'_report.json')).write_text(json.dumps(report,indent=2))
        probe.hide_render=False
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(args.variant+'_'+args.kind.lower()+'_benchmark.blend')),compress=True)
print('FOLIAGE_BENCHMARK_COMPLETE',flush=True)
