"""Bounded experiments: matched sun/sky and EEVEE irradiance volume capture."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import biome, lod

parser = argparse.ArgumentParser()
parser.add_argument('--site', default='Forest')
parser.add_argument('--variants', default='legacy,probe,sky,skyprobe')
parser.add_argument('--exposure', type=float, default=0.)
parser.add_argument('--sky-strength', type=float, default=.035)
parser.add_argument('--probe-resolution', type=int, default=16)
parser.add_argument('--bake-samples', type=int, default=128)
parser.add_argument('--prefix', default='')
parser.add_argument('--fine-shadows', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = ROOT / 'output/next-realism'
OUT.mkdir(parents=True, exist_ok=True)
fixture = OUT / ('fixture_' + args.site.lower() + '.blend')
bpy.ops.wm.open_mainfile(filepath=str(fixture if fixture.exists() else ROOT / 'dist/Open-Planet-Designer-Beta-Demo.blend'))
s = bpy.context.scene
r = next(o for o in s.objects if o.get('op_root'))
s.camera = bpy.data.objects['Entry Camera · ' + args.site]
s.frame_set(240)
r['lod_auto'] = False
if not fixture.exists():
    lod.update(s, r, True)
    bpy.ops.wm.save_as_mainfile(filepath=str(fixture), compress=True)
lod.unregister()
if bpy.app.timers.is_registered(lod._timer):
    bpy.app.timers.unregister(lod._timer)
s.render.resolution_x = 960
s.render.resolution_y = 540
s.render.resolution_percentage = 100
s.eevee.taa_render_samples = 64
s.eevee.shadow_pool_size = '512'
s.cycles.samples = 128
s.cycles.use_denoising = True
s.cycles.transparent_max_bounces = 64
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
s.cycles.device = 'GPU'
s.view_settings.exposure = args.exposure
bpy.context.view_layer.update()
cp, _ = lod.logical_camera(r, s.camera.evaluated_get(bpy.context.evaluated_depsgraph_get()))
up = (r.matrix_world.to_quaternion() @ cp.normalized()).normalized()
east = Vector((0, 0, 1)).cross(up).normalized()
north = up.cross(east).normalized()
sun = next(o for o in r.children if o.get('op_biome_light') == 'Sun')
if args.fine_shadows:
    s.eevee.shadow_pool_size = '1024'
    s.eevee.shadow_ray_count = 16
    s.eevee.shadow_step_count = 32
    s.eevee.taa_render_samples = 256
    sun.data.shadow_maximum_resolution = .005 / s.unit_settings.scale_length
sun_vector = -(sun.matrix_world.to_quaternion() @ Vector((0, 0, -1)))
report = {'site': args.site, 'exposure': args.exposure, 'sky_strength': args.sky_strength, 'renders': {}, 'bakes': {}}
original_world = s.world
original_fill = [(o, o.data.energy) for o in r.children if o.get('op_biome_light') in {'Sky fill', 'Horizon fill'}]

def daylight():
    world = bpy.data.worlds.new('Development · Matched daylight')
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    coord = tree.nodes.new('ShaderNodeTexCoord')
    combine = tree.nodes.new('ShaderNodeCombineXYZ')
    for i, axis in enumerate((east, north, up)):
        dot = tree.nodes.new('ShaderNodeVectorMath')
        dot.operation = 'DOT_PRODUCT'
        dot.inputs[1].default_value = axis
        tree.links.new(coord.outputs['Generated'], dot.inputs[0])
        tree.links.new(dot.outputs['Value'], combine.inputs[i])
    sky = tree.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.asin(max(-1, min(1, sun_vector.dot(up))))
    sky.sun_rotation = math.atan2(sun_vector.dot(north), sun_vector.dot(east))
    sky.altitude = max(0, min(100000, (cp.length - 1) * 6371000))
    sky.air_density = 1
    sky.aerosol_density = .35
    sky.ozone_density = 1
    tree.links.new(combine.outputs[0], sky.inputs['Vector'])
    background = tree.nodes.new('ShaderNodeBackground')
    background.inputs['Strength'].default_value = args.sky_strength
    tree.links.new(sky.outputs['Color'], background.inputs['Color'])
    output = tree.nodes.new('ShaderNodeOutputWorld')
    tree.links.new(background.outputs[0], output.inputs['Surface'])
    s.world = world
    for o, _ in original_fill:
        o.data.energy = 0

def volume():
    data = bpy.data.lightprobes.new('Development · Forest light capture', 'VOLUME')
    ob = bpy.data.objects.new(data.name, data)
    s.collection.objects.link(ob)
    data.resolution_x = args.probe_resolution
    data.resolution_y = args.probe_resolution
    data.resolution_z = args.probe_resolution // 2
    data.bake_samples = args.bake_samples
    data.surfel_density = args.probe_resolution * 2
    data.capture_world = True
    data.capture_indirect = True
    data.capture_emission = False
    data.clamp_indirect = 0
    metres = s.unit_settings.scale_length
    # A narrow foreground patch inside a larger tree stand. Dimensions and
    # capture distance are finite and expressed in physical scene units.
    basis = Matrix((east, north, up)).transposed().to_4x4()
    center = s.camera.matrix_world.translation + up * (10 / metres)
    ob.matrix_world = Matrix.Translation(center) @ basis @ Matrix.Diagonal((45/metres, 45/metres, 18/metres, 1))
    data.capture_distance = 40 / metres
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    s.render.engine = 'BLENDER_EEVEE'
    start = time.perf_counter()
    choices = [item.identifier for item in bpy.ops.object.lightprobe_cache_bake.get_rna_type().properties['subset'].enum_items]
    result = bpy.ops.object.lightprobe_cache_bake(subset='SELECTED' if 'SELECTED' in choices else 'ACTIVE')
    report['bakes'][current] = {'seconds': time.perf_counter() - start, 'result': list(result)}
    print('DAYLIGHT_BAKE', current, report['bakes'][current], flush=True)
    return ob

probe = None
for current in args.variants.split(','):
    if probe:
        bpy.data.objects.remove(probe, do_unlink=True)
        probe = None
    if current.startswith('sky'):
        daylight()
    else:
        s.world = original_world
        for ob, energy in original_fill:
            ob.data.energy = energy
    if current in {'probe', 'skyprobe'}:
        probe = volume()
    engines = [('BLENDER_EEVEE', 'eevee')] if current in {'probe', 'skyprobe'} else [('BLENDER_EEVEE', 'eevee'), ('CYCLES', 'cycles')]
    for engine, name in engines:
        s.render.engine = engine
        s.render.filepath = str(OUT / (args.prefix + args.site.lower() + '_' + current + '_' + name + '.png'))
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        report['renders'][current + '_' + name] = round(time.perf_counter() - start, 3)
        print('DAYLIGHT_RENDER', current, name, report['renders'][current + '_' + name], flush=True)
    (OUT / (args.prefix + 'daylight_' + args.site.lower() + '.json')).write_text(json.dumps(report, indent=2))
print('DAYLIGHT_COMPLETE', flush=True)
