# SPDX-License-Identifier: GPL-3.0-or-later
"""Physically sized CC0 substrate layers with shared color/height/roughness masks."""
from pathlib import Path
import bpy
from . import nodes as nd
from .look_math import texture_phase

# Poly Haven's /info dimensions are millimetres. Rounded scan footprints below
# retain the measured 2 m / 1.3 m / 1.8 m extents, with an explicit user scale.
LAYERS = (('leafy_grass', 2.), ('forrest_ground_01', 2.),
          ('brown_mud_leaves_01', 1.3), ('rock_boulder_dry', 1.8))


def update_phases(scene, root):
    radius_m = root['radius'] * scene.unit_settings.scale_length
    origin = tuple(root.get('op_anchor_' + a, 0.) for a in 'xyz')
    scale = root.get('look_texture_scale', 1.)
    root['op_metres_per_scene_unit'] = scene.unit_settings.scale_length
    for name, width in LAYERS:
        for axis, value in zip('xyz', texture_phase(origin, radius_m, width * scale)):
            root['op_ground_phase_' + name + '_' + axis] = value


def field(g, key, root):
    node = g.node('ShaderNodeValue', key)
    nd.drive(node.outputs[0], root, key)
    return node.outputs[0]


def layer(g, root, p, local_position, name, width):
    metres = field(g, 'op_metres_per_scene_unit', root)
    frequency = g.math('DIVIDE', g.math('MULTIPLY', p['radius'], metres), g.math('MULTIPLY', width, p['look_texture_scale']))
    phase = g.combine(*(field(g, 'op_ground_phase_' + name + '_' + a, root) for a in 'xyz'))
    coords = g.vec('ADD', g.vec('SCALE', local_position, scale=frequency), phase)
    result = {}
    for channel in ('color', 'height', 'roughness'):
        path = Path(__file__).parent / 'assets/ground' / (name + '_' + channel + ('.jpg' if channel == 'color' else '.png'))
        image = bpy.data.images.load(str(path), check_existing=True)
        image.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        if not image.packed_file:
            image.pack()
        node = g.node('ShaderNodeTexImage', 'Substrate · ' + name + ' · ' + channel)
        node.image = image
        node.projection = 'BOX'
        node.projection_blend = .3
        g.put(coords, node.inputs['Vector'])
        result[channel] = node.outputs['Color']
    return result


def fields(g, root, p, local_position, direction, biome, normal):
    radial = g.node('ShaderNodeVectorTransform', 'Geographic up', vector_type='NORMAL', convert_from='OBJECT', convert_to='WORLD')
    g.put(direction, radial.inputs[0])
    cosine = g.vec('DOT_PRODUCT', normal, g.vec('NORMALIZE', radial.outputs[0]))
    # Macro fields are geographic; high-frequency scan maps use the wrapped
    # local coordinates above so rebasing does not slide the photographed grain.
    patch_frequency = g.math('DIVIDE', g.math('MULTIPLY', p['radius'], field(g, 'op_metres_per_scene_unit', root)), 45.)
    patch = g.noise(direction, patch_frequency, 2., .6, 0., p['seed'])
    steep = g.math('SUBTRACT', 1., g.smooth(cosine, .57, .88))
    rock = g.math('MAXIMUM', steep, g.math('MAXIMUM', g.math('MULTIPLY', biome['mountain'], .52), g.math('MULTIPLY', biome['desert'], .38)))
    wet = g.math('MULTIPLY', p['look_moisture'], g.math('MULTIPLY_ADD', patch, .65, .35))
    wet = g.math('MULTIPLY', wet, g.math('MULTIPLY', g.smooth(cosine, .65, .96), g.math('SUBTRACT', 1., g.math('MULTIPLY', biome['desert'], .9))))
    soil = g.math('SUBTRACT', 1., rock)
    dry_soil = g.math('MULTIPLY', soil, g.math('SUBTRACT', 1., wet))
    weights = (g.math('MULTIPLY', dry_soil, g.math('SUBTRACT', 1., biome['forest'])),
               g.math('MULTIPLY', dry_soil, biome['forest']), g.math('MULTIPLY', soil, wet), rock)
    layers = [layer(g, root, p, local_position, name, width) for name, width in LAYERS]
    result = {}
    for channel in ('color', 'roughness', 'height'):
        mixed = (0., 0., 0.)
        for data, weight in zip(layers, weights):
            mixed = g.vec('ADD', mixed, g.vec('SCALE', data[channel], scale=weight))
        result[channel] = mixed
    # Water darkens the substrate and lowers roughness coherently; it is not AO.
    result['color'] = g.vec('SCALE', result['color'], scale=g.math('SUBTRACT', 1., g.math('MULTIPLY', wet, .28)))
    rough = g.math('MULTIPLY', result['roughness'], g.math('SUBTRACT', 1., g.math('MULTIPLY', wet, .40)))
    result['roughness'] = g.math('MINIMUM', .95, g.math('MAXIMUM', rough, .18))
    result['slope'] = cosine
    result['wetness'] = wet
    return result
