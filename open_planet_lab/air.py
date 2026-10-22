# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared spherical aerial perspective for the generated PBR surfaces."""
from . import nodes as nd
from . import ground


def properties(g, root):
    values = {}
    for key in ('op_metres_per_scene_unit', 'look_air_density', 'look_aerosol', 'op_air_capture_bypass'):
        n = g.node('ShaderNodeValue', key)
        nd.drive(n.outputs[0], root, key)
        values[key] = n.outputs[0]
    return values


def path(g, root, radius, point, direction, distance):
    """Split each clipped ray at its nearest approach; quadrature is quadratic."""
    data = properties(g, root)
    radius_m = g.math('MULTIPLY', radius, data['op_metres_per_scene_unit'])
    b = g.vec('DOT_PRODUCT', point, direction)
    o2 = g.vec('DOT_PRODUCT', point, point)
    outer = g.math('ADD', 1., g.math('DIVIDE', 10000., g.math('MULTIPLY', radius_m, .1)))
    disc = g.math('ADD', g.math('MULTIPLY', b, b), g.math('SUBTRACT', g.math('MULTIPLY', outer, outer), o2))
    sq = g.math('SQRT', g.math('MAXIMUM', disc, 0.))
    minus = g.math('MULTIPLY', b, -1.)
    start = g.math('MAXIMUM', 0., g.math('SUBTRACT', minus, sq))
    end = g.math('MINIMUM', distance, g.math('ADD', minus, sq))
    extent = g.math('MAXIMUM', 0., g.math('SUBTRACT', end, start))
    closest = g.math('MINIMUM', end, g.math('MAXIMUM', start, minus))
    accum_r = accum_m = 0.
    for sign, length in ((-1., g.math('MAXIMUM', 0., g.math('SUBTRACT', closest, start))),
                         (1., g.math('MAXIMUM', 0., g.math('SUBTRACT', end, closest)))):
        for i in range(24):
            a, b2 = (i/24)**2, ((i+1)/24)**2
            t = g.math('ADD', closest, g.math('MULTIPLY', length, sign*(a+b2)*.5))
            sample = g.vec('ADD', point, g.vec('SCALE', direction, scale=t))
            h = g.math('MULTIPLY', g.math('MAXIMUM', 0., g.math('SUBTRACT', g.vec('LENGTH', sample), 1.)), radius_m)
            ds = g.math('MULTIPLY', g.math('MULTIPLY', length, b2-a), radius_m)
            rho_r = g.math('EXPONENT', g.math('DIVIDE', h, -8000.))
            rho_m = g.math('EXPONENT', g.math('DIVIDE', h, -1200.))
            accum_r = g.math('ADD', accum_r, g.math('MULTIPLY', ds, rho_r))
            accum_m = g.math('ADD', accum_m, g.math('MULTIPLY', ds, rho_m))
    tau = g.math('ADD', g.math('MULTIPLY', accum_r, g.math('MULTIPLY', data['look_air_density'], .0000175)),
                 g.math('MULTIPLY', accum_m, g.math('MULTIPLY', data['look_aerosol'], .00002)))
    valid = g.math('MULTIPLY', g.math('GREATER_THAN', disc, 0.), g.math('GREATER_THAN', extent, 0.))
    opacity = g.math('MULTIPLY', valid, g.math('SUBTRACT', 1., g.math('EXPONENT', g.math('MULTIPLY', tau, -1.))))
    return opacity, data


def group(root, daylight_group):
    tree = nd.bpy.data.node_groups.new(root.name + ' · Shared aerial perspective', 'ShaderNodeTree')
    tree['op_air_owner'] = root.name
    tree.interface.new_socket(name='Surface', in_out='INPUT', socket_type='NodeSocketShader')
    alpha = tree.interface.new_socket(name='Alpha', in_out='INPUT', socket_type='NodeSocketFloat')
    alpha.default_value = 1.
    tree.interface.new_socket(name='Surface', in_out='OUTPUT', socket_type='NodeSocketShader')
    g = nd.Graph(tree)
    inp = g.node('NodeGroupInput')
    out = g.node('NodeGroupOutput')
    coords = g.node('ShaderNodeTexCoord', 'Planet coordinates')
    coords.object = root
    geo = g.node('ShaderNodeNewGeometry')
    cam = g.node('ShaderNodeCameraData')
    rnode = g.node('ShaderNodeValue', 'Planet radius')
    nd.drive(rnode.outputs[0], root, 'radius')
    radius = rnode.outputs[0]
    # OBJECT space here would be the tree instance's space. Use the planet's
    # explicit orthonormal basis for every surface, including instanced leaves.
    axes = [g.combine(*(ground.field(
        g,'op_planet_axis_'+axis+'_'+component,root) for component in 'xyz')) for axis in 'xyz']
    incoming = g.vec('NORMALIZE',g.combine(*(g.vec('DOT_PRODUCT',geo.outputs['Incoming'],axis) for axis in axes)))
    distance = g.math('DIVIDE', cam.outputs['View Distance'], radius)
    origin = g.vec('ADD', coords.outputs['Object'], g.vec('SCALE', incoming, scale=distance))
    ray = g.vec('SCALE', incoming, scale=-1.)
    opacity, data = path(g, root, radius, origin, ray, distance)
    # Use the same horizon radiance as the visible sky. This scalar extinction
    # approximation preserves shader energy and alpha; spectral transport is open.
    up = []
    for axis in 'xyz':
        n = g.node('ShaderNodeValue', 'World up ' + axis)
        nd.drive(n.outputs[0], root, 'op_sky_up_' + axis)
        up.append(n.outputs[0])
    up = g.combine(*up)
    forward = g.vec('SCALE', geo.outputs['Incoming'], scale=-1.)
    horizontal = g.vec('SUBTRACT', forward, g.vec('SCALE', up, scale=g.vec('DOT_PRODUCT', forward, up)))
    horizon = g.vec('NORMALIZE', g.vec('ADD', horizontal, g.vec('SCALE', up, scale=.08)))
    sky = g.node('ShaderNodeGroup', 'Shared horizon radiance')
    sky.node_tree = daylight_group
    g.put(horizon, sky.inputs['Direction'])
    emission = nd.emission(g, sky.outputs['Ground radiance'])
    lp = g.node('ShaderNodeLightPath')
    weight = g.math('MULTIPLY', opacity, g.math('MULTIPLY', lp.outputs['Is Camera Ray'], g.math('SUBTRACT', 1., data['op_air_capture_bypass'])))
    fog = g.node('ShaderNodeMixShader', 'View transmittance and in-scattering')
    g.put(weight, fog.inputs[0])
    g.put(inp.outputs['Surface'], fog.inputs[1])
    g.put(emission, fog.inputs[2])
    transparent = g.node('ShaderNodeBsdfTransparent')
    mask = g.node('ShaderNodeMixShader', 'Preserve original leaf coverage')
    g.put(inp.outputs['Alpha'], mask.inputs[0])
    g.put(transparent.outputs[0], mask.inputs[1])
    g.put(fog.outputs[0], mask.inputs[2])
    g.put(mask.outputs[0], out.inputs['Surface'])
    root['op_air_group'] = tree.name
    return tree


def wrap(g, root, shader, alpha=1.):
    from . import lookdev
    tree = nd.bpy.data.node_groups.get(root.get('op_air_group', ''))
    if tree is None:
        tree = group(root, lookdev.daylight_group(root))
    node = g.node('ShaderNodeGroup', 'Shared planetary aerial perspective')
    node.node_tree = tree
    g.put(shader, node.inputs['Surface'])
    g.put(alpha, node.inputs['Alpha'])
    return node.outputs['Surface']


def shell(root):
    """Back boundary only: opaque terrain occludes it, avoiding doubled haze."""
    from . import lookdev
    m,g=nd.material(root.name+' · Development clear-air boundary')
    coords=g.node('ShaderNodeTexCoord');coords.object=root
    geo=g.node('ShaderNodeNewGeometry');cam=g.node('ShaderNodeCameraData')
    radius=ground.field(g,'radius',root)
    axes=[g.combine(*(ground.field(g,'op_planet_axis_'+a+'_'+c,root) for c in 'xyz')) for a in 'xyz']
    incoming=g.vec('NORMALIZE',g.combine(*(g.vec('DOT_PRODUCT',geo.outputs['Incoming'],a) for a in axes)))
    distance=g.math('DIVIDE',cam.outputs['View Distance'],radius)
    origin=g.vec('ADD',coords.outputs['Object'],g.vec('SCALE',incoming,scale=distance))
    opacity,_=path(g,root,radius,origin,g.vec('SCALE',incoming,scale=-1.),distance)
    up=g.combine(*(ground.field(g,'op_sky_up_'+a,root) for a in 'xyz'))
    forward=g.vec('SCALE',geo.outputs['Incoming'],scale=-1.)
    horizontal=g.vec('SUBTRACT',forward,g.vec('SCALE',up,scale=g.vec('DOT_PRODUCT',forward,up)))
    horizon=g.vec('NORMALIZE',g.vec('ADD',horizontal,g.vec('SCALE',up,scale=.08)))
    sky=g.node('ShaderNodeGroup','Shared limb radiance');sky.node_tree=lookdev.daylight_group(root)
    g.put(horizon,sky.inputs['Direction'])
    weight=g.math('SUBTRACT',1.,ground.field(g,'op_daylight_sky_weight',root))
    opacity=g.math('MULTIPLY',opacity,weight)
    lp=g.node('ShaderNodeLightPath')
    opacity=g.math('MULTIPLY',opacity,lp.outputs['Is Camera Ray'])
    return nd.add_transparency(g,m,sky.outputs['Ground radiance'],opacity,False,facing=geo.outputs['Backfacing'])
