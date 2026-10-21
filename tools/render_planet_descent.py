"""Render one continuous bounded orbit-to-grassland descent, with cached detail."""
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
from open_planet_lab import biome, lod, lod_mesh

parser = argparse.ArgumentParser()
parser.add_argument('--probe', action='store_true')
parser.add_argument('--samples', type=int, default=24)
parser.add_argument('--start', type=int, default=1)
parser.add_argument('--end', type=int, default=576)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = ROOT / 'output/planets/beta/descent'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'output/planets/realism/Open_Planet_Realism_Priorities.blend'))
lod.unregister()
s = bpy.context.scene
r = next(o for o in s.objects if o.get('op_root'))
s.camera = bpy.data.objects['Entry Camera · Grassland']
s.frame_set(240)
r.op_lod.camera = None
r['lod_auto'] = False
lod.update(s, r, True)
source = s.camera
dg = bpy.context.evaluated_depsgraph_get()
cp, _ = lod.logical_camera(r, source.evaluated_get(dg))
direction = cp.normalized()
ground = biome.sample(s, r, [tuple(direction)])[0][0].length
reference = source.copy()
reference.data = source.data.copy()
reference.name = 'Beta Descent · Locked detail reference'
s.collection.objects.link(reference)
reference.animation_data_clear()
for group in bpy.data.node_groups:
    node = group.nodes.get('LOD Camera')
    if node and 'Object' in node.inputs:
        node.inputs['Object'].default_value = reference
cam = source.copy()
cam.data = source.data.copy()
cam.name = 'Beta Descent Camera'
s.collection.objects.link(cam)
cam.animation_data_clear()
s.camera = cam
r['lod_enabled'] = False
r['op_lod_status'] = 'Bounded descent geometry cached at the destination'
cam.data.dof.use_dof = False
s.render.engine = 'BLENDER_EEVEE'
s.eevee.taa_render_samples = args.samples
s.eevee.shadow_pool_size = '512'
s.render.resolution_x = 1280
s.render.resolution_y = 720
s.render.resolution_percentage = 100
s.render.fps = 24
s.render.fps_base = 1
s.render.use_persistent_data = True
s.render.use_motion_blur = False
s.render.use_compositing = False
s.render.use_sequencer = False
s.render.film_transparent = False
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.frame_start = 1
s.frame_end = 576
radius = float(r['radius'])
physical_radius = radius * s.unit_settings.scale_length
tangent = (Vector((0, 0, 1)) - direction * direction.z).normalized()
rotation = r.matrix_local.to_quaternion()

def pose(t):
    # Monotone Hermite interpolation in log altitude leaves time for vegetation
    # and eases the beginning/end, while preserving one continuous camera move.
    knots = [0., .22, .38, .65, 1.]
    heights = [math.log(v) for v in (physical_radius * 3, 100000., 1000., 35., 2.2)]
    slopes = [(heights[i+1]-heights[i])/(knots[i+1]-knots[i]) for i in range(4)]
    derivatives = [0.] + [2*slopes[i-1]*slopes[i]/(slopes[i-1]+slopes[i]) for i in range(1,4)] + [0.]
    segment = min(3, next((i for i in range(4) if t <= knots[i+1]), 3))
    span = knots[segment+1] - knots[segment]
    u = (t - knots[segment])/span
    log_altitude = ((2*u**3-3*u**2+1)*heights[segment]
        +(u**3-2*u**2+u)*span*derivatives[segment]
        +(-2*u**3+3*u**2)*heights[segment+1]
        +(u**3-u**2)*span*derivatives[segment+1])
    altitude = math.exp(log_altitude)
    position = direction * (ground + altitude / physical_radius)
    blend = lod_mesh.smooth((t - .14) / .24)
    ray = (-direction * (1 - blend * .88) + tangent * blend).normalized()
    up = direction - ray * direction.dot(ray)
    if up.length < .001:
        up = tangent
    right = ray.cross(up).normalized()
    up = right.cross(ray).normalized()
    logical_rotation = Matrix((right, up, -ray)).transposed().to_quaternion()
    return altitude, position, rotation @ logical_rotation

# Sky strength must follow the moving render camera, independently of the
# fixed geometry reference. The bounded origin remains fixed for this shot.
sky = s.world.node_tree.nodes.get('Interior photographic background')
if sky:
    curve = sky.inputs['Strength'].driver_add('default_value')
    curve.driver.type = 'SCRIPTED'
    variable = curve.driver.variables.new()
    variable.name = 'weight'
    variable.type = 'SINGLE_PROP'
    variable.targets[0].id = r
    variable.targets[0].data_path = '["op_sky_weight"]'
    curve.driver.expression = '.7 * weight'

records = []
for index in range(576):
    frame = index + 1
    altitude, position, quaternion = pose(index / 575)
    cam.location = r.matrix_local @ position
    cam.rotation_euler = quaternion.to_euler()
    cam.keyframe_insert('location', frame=frame)
    cam.keyframe_insert('rotation_euler', frame=frame)
    inside = bool(r['atmosphere'] and position.length < 1 + r['atmosphere_height'])
    weight = (1 - lod_mesh.smooth((position.length - 1 - .0015) / max(.0001, r['atmosphere_height'] - .0015))) if r['atmosphere'] else 0
    for name, value in [('op_inside_sky', float(inside)), ('op_sky_weight', weight), ('op_living_cloud_visibility', 1 - weight)]:
        r[name] = value
        r.keyframe_insert('[' + json.dumps(name) + ']', frame=frame)
    for ob in r.children:
        if ob.get('op_role') == 'ATMOSPHERE':
            ob.hide_render = not r['atmosphere'] or inside
            ob.keyframe_insert('hide_render', frame=frame)
    if inside:
        h = max(0, position.length - ground)
        horizon = math.sqrt(max(0, 2 * h + h * h))
        cam.data.clip_end = radius * max(r.get('biome_view_distance', .001), horizon * 1.25)
    else:
        cam.data.clip_end = radius * max(position.length + 2, 3)
    cam.data.clip_start = max(.000001, radius * .000000001, cam.data.clip_end * .000001)
    cam.data.keyframe_insert('clip_start', frame=frame)
    cam.data.keyframe_insert('clip_end', frame=frame)
    records.append({'frame': frame, 'altitude_m': altitude, 'sky_weight': weight})
for ob in (cam, r):
    for fc in biome.curves(ob):
        for key in fc.keyframe_points:
            key.interpolation = 'LINEAR'

s['op_note'] = 'Open Planet Designer beta | continuous bounded descent | AI-assisted'
s.frame_set(576)
bpy.context.view_layer.update()
report = {'fps': 24, 'frames': 576, 'resolution': [1280, 720], 'samples': args.samples,
          'route': 'One continuous orbital-to-grassland descent', 'geometry_cached_at_destination': True,
          'terrain_triangles': int(r['op_lod_triangles']), 'scatter_triangles': int(r['op_biome_triangles']),
          'instances': int(r['op_biome_instances']), 'path': records, 'render_times': []}
(OUT / 'route.json').write_text(json.dumps(report, indent=2))
indices = [0, 150, 260, 380, 460, 575] if args.probe else range(args.start - 1, args.end)
for index in indices:
    path = OUT / ('frame_%04d.png' % (index + 1))
    if path.exists() and not args.probe:
        continue
    s.frame_set(index + 1)
    bpy.context.view_layer.update()
    s.render.filepath = str(path)
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    item = {'frame': index + 1, 'seconds': round(time.perf_counter() - started, 3)}
    report['render_times'].append(item)
    (OUT / ('probe.json' if args.probe else 'render_%03d_%03d.json' % (args.start, args.end))).write_text(json.dumps(report, indent=2))
    print('DESCENT_FRAME', json.dumps(item), flush=True)
print('DESCENT_COMPLETE', flush=True)
