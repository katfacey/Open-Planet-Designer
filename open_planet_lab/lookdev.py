# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in matched Earth daylight, finite baked indirect light and shared air.

The probe is a static-shot approximation. No engine-specific material gains
are used. Clear-air extinction is scalar; full spectral/cloud transport is open.
"""
import array
import hashlib
import json
import math
import bpy
from mathutils import Matrix, Vector
from . import nodes as nd
from .presets import BASE
from .presets import LABELS, RANGES
from . import ground
from .look_math import smooth

VERSION = 1


def ensure(scene, root):
    for key, value in BASE.items():
        if key not in root:
            root[key] = value
        if key.startswith('look_') and not isinstance(value,bool):
            lo,hi=RANGES[key]
            root.id_properties_ui(key).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description=LABELS[key])
    ground.update_phases(scene, root)
    root['op_air_shell_scale']=1.+100000./(root['radius']*scene.unit_settings.scale_length)
    root['op_air_capture_bypass'] = root.get('op_air_capture_bypass', 0.)
    for axis, vector in zip('xyz', ((1,0,0),(0,1,0),(0,0,1))):
        for component, value in zip('xyz', vector):
            key = 'op_planet_axis_' + axis + '_' + component
            if key not in root:
                root[key] = float(value)
    for name, vector in (('east',(1,0,0)),('north',(0,1,0)),('up',(0,0,1))):
        for axis, value in zip('xyz', vector):
            key = 'op_sky_' + name + '_' + axis
            if key not in root:
                root[key] = float(value)


def daylight_group(root):
    tree = bpy.data.node_groups.get(root.get('op_daylight_group', ''))
    if tree and tree.get('op_daylight_version') == VERSION:
        return tree
    tree = bpy.data.node_groups.new(root.name + ' · Shared daylight', 'ShaderNodeTree')
    tree['op_daylight_version'] = VERSION
    tree.interface.new_socket(name='Direction', in_out='INPUT', socket_type='NodeSocketVector')
    for name in ('Ground radiance','Visible radiance'):
        tree.interface.new_socket(name=name, in_out='OUTPUT', socket_type='NodeSocketColor')
    g = nd.Graph(tree)
    inp = g.node('NodeGroupInput')
    out = g.node('NodeGroupOutput')
    axes = []
    for name in ('east','north','up'):
        values = [ground.field(g,'op_sky_'+name+'_'+a,root) for a in 'xyz']
        axes.append(g.vec('DOT_PRODUCT',inp.outputs['Direction'],g.combine(*values)))
    local = g.combine(*axes)
    strength = g.math('MULTIPLY',ground.field(g,'look_sky_strength',root),ground.field(g,'exposure',root))
    weight = ground.field(g,'op_daylight_sky_weight',root)
    for name, output_name in (('Ground sky','Ground radiance'),('Camera sky','Visible radiance')):
        sky = g.node('ShaderNodeTexSky',name)
        sky.sky_type = 'MULTIPLE_SCATTERING'
        sky.sun_disc = False
        g.put(local,sky.inputs['Vector'])
        color = g.vec('SCALE',sky.outputs['Color'],scale=strength)
        if name == 'Camera sky':
            color = g.vec('SCALE',color,scale=weight)
        g.put(color,out.inputs[output_name])
    root['op_daylight_group'] = tree.name
    return tree


def environment(scene, root, ground_radius=None):
    """Keep geographic sun/up consistent without relighting ground as we fly."""
    ensure(scene,root)
    from .lod import camera_for, logical_camera
    cam = camera_for(scene,root)
    dg=bpy.context.evaluated_depsgraph_get()
    cp = logical_camera(root,cam.evaluated_get(dg))[0] if cam else Vector((0,0,1))
    view_cp=logical_camera(root,scene.camera.evaluated_get(dg))[0] if scene.camera else cp
    rotation = root.matrix_world.to_quaternion()
    up = (rotation @ cp.normalized()).normalized()
    east = Vector((0,0,1)).cross(up)
    east = east.normalized() if east.length > 1e-6 else Vector((1,0,0))
    north = up.cross(east).normalized()
    for name, vector in (('east',east),('north',north),('up',up)):
        for axis, value in zip('xyz',vector):
            root['op_sky_'+name+'_'+axis] = float(value)
    for axis, vector in zip('xyz',(Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))):
        for component, value in zip('xyz',rotation @ vector):
            root['op_planet_axis_'+axis+'_'+component] = float(value)
    metres = root['radius']*scene.unit_settings.scale_length
    altitude = max(0.,(view_cp.length-1.)*metres)
    root['op_camera_altitude_m'] = altitude
    # A finite clear-air sphere is handed over continuously to the visible sky.
    root['op_daylight_sky_weight'] = 1.-smooth(altitude,80000.,100000.)
    if ground_radius is not None:
        root['op_ground_altitude_m'] = max(0.,(ground_radius-1.)*metres)
    az, el = math.radians(root['sun_azimuth']),math.radians(root['sun_elevation'])
    sun = rotation @ Vector((math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)))
    tree = daylight_group(root)
    for name, height in (('Ground sky',root.get('op_ground_altitude_m',0.)),('Camera sky',altitude)):
        sky = tree.nodes[name]
        sky.sun_elevation = math.asin(max(-1.,min(1.,sun.dot(up))))
        sky.sun_rotation = math.atan2(sun.dot(north),sun.dot(east))
        sky.altitude = max(0.,min(100000.,height))
        sky.air_density = root['look_air_density']
        sky.aerosol_density = root['look_aerosol']
        sky.ozone_density = 1.
    world = scene.world
    if not world or world.get('op_daylight_owner') != root.name:
        previous = world
        world = bpy.data.worlds.new(root.name+' · Shared Earth daylight')
        world.use_nodes = True
        world['op_daylight_owner'] = root.name
        if previous:world['op_previous_world'] = previous.name
        scene.world = world
        world.node_tree.nodes.clear()
        g = nd.Graph(world.node_tree)
        coord = g.node('ShaderNodeTexCoord')
        shared = g.node('ShaderNodeGroup','Shared daylight');shared.node_tree=tree
        g.put(coord.outputs['Generated'],shared.inputs['Direction'])
        bg = g.node('ShaderNodeBackground')
        lp = g.node('ShaderNodeLightPath')
        col = g.mix(lp.outputs['Is Camera Ray'],shared.outputs['Ground radiance'],shared.outputs['Visible radiance'])
        g.put(col,bg.inputs['Color'])
        out = g.node('ShaderNodeOutputWorld');g.put(bg.outputs[0],out.inputs['Surface'])
    tree.update_tag();root.update_tag();world.update_tag()


def lighting(scene, root):
    # Called after the legacy creator has ensured the linked Sun exists.
    for ob in root.children:
        if ob.get('op_biome_light') in {'Sky fill','Horizon fill'}:
            ob.data.energy = 0.
        elif ob.get('op_biome_light') == 'Sun':
            altitude=max(0.,root.get('op_camera_altitude_m',0.)-root.get('op_ground_altitude_m',0.))
            height=scene.render.resolution_y*scene.render.resolution_percentage/100
            focal=height/max(2*math.tan(scene.camera.data.angle_y*.5),1e-6) if scene.camera else height
            texel=max(root['look_shadow_texel'],altitude*2./max(focal,1.))
            ob.data.shadow_maximum_resolution=texel/scene.unit_settings.scale_length
    scene.eevee.use_raytracing = True
    scene.eevee.shadow_ray_count = 8
    scene.eevee.shadow_step_count = 16


def wrap_assets(root):
    """Preserve source PBR and alpha. Unsupported compound alpha is left alone."""
    from . import air
    seen=set();wrapped=0;skipped=[]
    for ob in root.children:
        if ob.get('op_role') != 'BIOME_SOURCE':continue
        for material in ob.data.materials:
            if not material or material.as_pointer() in seen:continue
            seen.add(material.as_pointer())
            if material.get('op_air_owner') == root.name:
                wrapped+=1
                continue
            if not material.use_nodes:skipped.append(material.name);continue
            tree=material.node_tree
            out=next((n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
            if not out or not out.inputs['Surface'].is_linked:continue
            source=out.inputs['Surface'].links[0].from_socket
            principles=[n for n in tree.nodes if n.type=='BSDF_PRINCIPLED']
            alpha=1.
            if len(principles)==1 and source.node==principles[0]:
                socket=principles[0].inputs['Alpha']
                alpha=socket.links[0].from_socket if socket.is_linked else socket.default_value
                for link in list(socket.links):tree.links.remove(link)
                socket.default_value=1.
            elif any(n.type=='BSDF_TRANSPARENT' for n in tree.nodes) or any(
                n.inputs['Alpha'].is_linked or n.inputs['Alpha'].default_value<1. for n in principles):
                skipped.append(material.name);continue
            g=nd.Graph(tree)
            g.put(air.wrap(g,root,source,alpha),out.inputs['Surface'])
            material['op_air_owner']=root.name;wrapped+=1
    root['op_air_material_status']=f'{wrapped} shared-air materials; {len(skipped)} unsupported'
    root['op_air_material_skipped']=json.dumps(skipped)


def shot_signature(scene, root, details=False):
    """Conservative static capture key, including geometry and external lights.

    Hash actual local vertex/placement arrays; an identical forced LOD rebuild
    remains valid. Camera detail, material edits and animated water invalidate.
    """
    from .lod import camera_for,logical_camera
    cam=camera_for(scene,root)
    digest=hashlib.sha256()
    sections={};section='settings'
    def emit(value):
        digest.update(value)
        sections.setdefault(section,hashlib.sha256()).update(value)
    def add(value):emit(repr(value).encode('utf-8'))
    add(VERSION)
    add([(k,tuple(root[k]) if k.endswith('_color') else root.get(k,v)) for k,v in BASE.items()])
    add(scene.unit_settings.scale_length)
    section='camera'
    if cam:
        cp,forward=logical_camera(root,cam.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        add(tuple(round(x,12) for x in cp));add(tuple(round(x,9) for x in forward))
        add((cam.data.lens,cam.data.type,cam.data.ortho_scale))
    add((scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage))
    materials=set()
    for ob in sorted(scene.objects,key=lambda x:x.name):
        if ob.type=='LIGHT':
            section='light: '+ob.name
            add((ob.name,tuple(x for row in ob.matrix_world for x in row),ob.data.energy,tuple(ob.data.color),ob.data.use_shadow))
        if ob.type!='MESH' or (ob.hide_render and ob.get('op_role')!='BIOME_SOURCE'):continue
        section='geometry: '+ob.name
        add((ob.name,ob.hide_render,tuple(round(x,9) for row in ob.matrix_local for x in row)))
        mesh=ob.data
        add((len(mesh.vertices),len(mesh.loops),len(mesh.polygons)))
        for collection,prop,count,kind in ((mesh.vertices,'co',3,'f'),(mesh.loops,'vertex_index',1,'i')):
            data=array.array(kind,[0])*(len(collection)*count)
            collection.foreach_get(prop,data);emit(data.tobytes())
        for name in ('op_rotation','op_scale','id'):
            attr=mesh.attributes.get(name)
            if attr:
                vector=attr.data_type=='FLOAT_VECTOR'
                data=array.array('f' if vector else 'i',[0])*(len(attr.data)*(3 if vector else 1))
                attr.data.foreach_get('vector' if vector else 'value',data);emit(data.tobytes())
        for mat in mesh.materials:
            if not mat or mat.as_pointer() in materials or not mat.use_nodes:continue
            section='material: '+mat.name
            materials.add(mat.as_pointer());add(mat.name)
            for node in mat.node_tree.nodes:
                add((node.name,node.bl_idname))
                for socket in node.inputs:
                    if not socket.is_linked and hasattr(socket,'default_value'):
                        val=socket.default_value
                        add((socket.name,tuple(val) if hasattr(val,'__len__') else str(val)))
                if node.type=='TEX_IMAGE' and node.image:
                    add((node.image.name,node.image.filepath,tuple(node.image.size),node.image.is_dirty))
            add([(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links])
    result=digest.hexdigest()
    return (result,{key:value.hexdigest() for key,value in sections.items()}) if details else result


def probe_for(root):
    return next((ob for ob in root.children if ob.get('op_role')=='DAYLIGHT_PROBE'),None)


def validate_capture(scene, root):
    probe=probe_for(root)
    if not probe:return False
    current,parts=shot_signature(scene,root,details=True)
    valid=probe.get('op_shot_signature')==current
    probe.hide_render=not valid;probe.hide_viewport=not valid
    root['op_gi_status']='Baked for current static shot' if valid else 'Lighting changed — bake current shot again'
    previous=json.loads(probe.get('op_shot_parts','{}'))
    root['op_gi_changed']=json.dumps([name for name in parts if parts[name]!=previous.get(name)]) if not valid else '[]'
    return valid


def bake(scene, root):
    if not root.get('look_enabled'):raise RuntimeError('Upgrade Daylight & Ground first')
    from . import biome,lod
    cam=lod.camera_for(scene,root)
    if not cam:raise RuntimeError('Choose a shot camera first')
    lod.update(scene,root)
    environment(scene,root);biome.lighting(scene,root);wrap_assets(root)
    probe=probe_for(root)
    if probe is None:
        data=bpy.data.lightprobes.new(root.name+' · Static shot indirect light','VOLUME')
        probe=bpy.data.objects.new(data.name,data);root.users_collection[0].objects.link(probe)
        probe.parent=root;probe['op_role']='DAYLIGHT_PROBE'
    probe.hide_render=False;probe.hide_viewport=False
    cp,_=lod.logical_camera(root,cam.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    up=cp.normalized();east=Vector((0,0,1)).cross(up)
    east=east.normalized() if east.length>1e-6 else Vector((1,0,0))
    north=up.cross(east).normalized()
    metres=root['radius']*scene.unit_settings.scale_length
    width=root['look_probe_extent']
    probe.location=cp+up*(10./metres)
    probe.rotation_euler=Matrix((east,north,up)).transposed().to_euler()
    probe.scale=(width*.5/metres,width*.5/metres,width*.2/metres)
    data=probe.data;resolution=int(root['look_probe_resolution'])
    data.resolution_x=data.resolution_y=resolution;data.resolution_z=max(2,resolution//2)
    data.bake_samples=int(root['look_probe_samples']);data.surfel_density=resolution*2
    data.capture_world=True;data.capture_indirect=True;data.capture_emission=False
    data.clamp_indirect=0.;data.intensity=1.
    data.capture_distance=root['look_probe_capture']/scene.unit_settings.scale_length
    selected=list(bpy.context.selected_objects);active=bpy.context.view_layer.objects.active
    engine=scene.render.engine
    succeeded=False
    probe['op_shot_signature']=''
    try:
        for ob in selected:ob.select_set(False)
        probe.select_set(True);bpy.context.view_layer.objects.active=probe
        scene.render.engine='BLENDER_EEVEE';root['op_air_capture_bypass']=1.
        bpy.context.view_layer.update()
        result=bpy.ops.object.lightprobe_cache_bake(subset='SELECTED')
        if 'FINISHED' not in result:raise RuntimeError('Blender did not finish the light capture')
        succeeded=True
    finally:
        root['op_air_capture_bypass']=0.;scene.render.engine=engine
        probe.select_set(False)
        for ob in selected:
            if ob.name in bpy.context.view_layer.objects:ob.select_set(True)
        bpy.context.view_layer.objects.active=active
        bpy.context.view_layer.update()
        if not succeeded:
            probe.hide_render=True;probe.hide_viewport=True
            root['op_gi_status']='Capture failed — bake current shot again'
    signature,parts=shot_signature(scene,root,details=True)
    probe['op_shot_signature']=signature
    probe['op_shot_parts']=json.dumps(parts)
    root['op_gi_status']='Baked for current static shot'
    return probe


def rebuild_materials(root):
    """Change appearance without rebuilding the unaffected terrain node graph."""
    controls=nd.controls(root);root['op_controls']=controls.name
    surface=nd.surface(root,controls,root['op_kind'])
    atmosphere=nd.atmosphere(root,controls,root['op_kind'])
    old=set()
    for ob in root.children:
        role=ob.get('op_role')
        if role not in {'SURFACE','FAR_SURFACE','ATMOSPHERE'}:continue
        old.update(mat for mat in ob.data.materials if mat)
        ob.data.materials.clear()
        ob.data.materials.append(atmosphere if role=='ATMOSPHERE' else surface)
    for mat in old:
        if mat.users==0:bpy.data.materials.remove(mat)


def enable(scene, root):
    if bpy.app.version < (5,2,0):raise RuntimeError('Development daylight requires Blender 5.2 or newer')
    if root.get('op_kind')!='ROCK' or not root.get('biome_enabled'):
        raise RuntimeError('Build a rocky living surface first')
    ensure(scene,root);root['look_enabled']=True
    from .generator import prop_driver
    shell=next((o for o in root.children if o.get('op_role')=='ATMOSPHERE'),None)
    if shell:
        for i in range(3):
            shell.driver_remove('scale',i)
            prop_driver(shell,'scale',i,root,'op_air_shell_scale','v')
    environment(scene,root)
    from . import lod
    rebuild_materials(root)
    wrap_assets(root)
    from . import biome
    biome.lighting(scene,root)
    lod.update(scene,root,True)
    root['op_gi_status']='Bake current static shot for Eevee indirect lighting'


def disable(scene, root):
    """Rebuild legacy shaders and restore the original alpha of bundled assets."""
    for ob in root.children:
        if ob.get('op_role')!='BIOME_SOURCE':continue
        for mat in ob.data.materials:
            if not mat or mat.get('op_air_owner')!=root.name:continue
            tree=mat.node_tree
            for node in list(tree.nodes):
                if node.type!='GROUP' or not node.node_tree or node.node_tree.get('op_air_owner')!=root.name:continue
                source=node.inputs['Surface'].links[0].from_socket
                alpha=node.inputs['Alpha']
                if source.node.type=='BSDF_PRINCIPLED':
                    nd.Graph(tree).put(alpha.links[0].from_socket if alpha.is_linked else alpha.default_value,source.node.inputs['Alpha'])
                for link in list(node.outputs['Surface'].links):tree.links.new(source,link.to_socket)
                tree.nodes.remove(node)
            del mat['op_air_owner']
    root['look_enabled']=False
    shell=next((o for o in root.children if o.get('op_role')=='ATMOSPHERE'),None)
    from . import generator
    if shell:
        for i in range(3):
            shell.driver_remove('scale',i)
            generator.prop_driver(shell,'scale',i,root,'atmosphere_height','1+v')
    probe=probe_for(root)
    if probe:probe.hide_render=True;probe.hide_viewport=True
    rebuild_materials(root)
    from . import lod,biome
    biome.setup_world(scene,root);biome.lighting(scene,root)
    lod.update(scene,root,True)
