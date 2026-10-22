# SPDX-License-Identifier: GPL-3.0-or-later
"""World-anchored surface ecology with shared model LODs and hard scatter caps."""
import math,random
from pathlib import Path
from collections import defaultdict
import bpy
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
from . import nodes as nd,lod_mesh
from .presets import BASE,LABELS,RANGES

MODES=[('0','Climate map','Climate controls the land biome'),('1','Grassland','Grass on land'),
       ('2','Forest','Pine woodland on land'),('3','Ocean','Ocean world'),
       ('4','Alpine','Mountain land'),('5','Desert','Canyon and rocky desert land')]

def ensure(root):
    for key,value in BASE.items():
        if key.startswith('biome_'):
            if key not in root:root[key]=value
            if isinstance(value,bool):root.id_properties_ui(key).update(description=LABELS[key])
            else:
                lo,hi=RANGES[key];root.id_properties_ui(key).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description=LABELS[key])

def rebase(scene,root,cam,cp):
    """Put the active surface cell near world zero; retain logical geography.

    All generator cameras share the origin parent. Ordinary scene props can be
    parented to this rig to participate in the same coordinate system.
    """
    rig=root.parent if root.parent and root.parent.get('op_floating_origin') else None
    if rig is None:
        rig=bpy.data.objects.new(root.name+' Â· Floating Origin',None)
        root.users_collection[0].objects.link(rig);rig['op_floating_origin']=True
        old=root.matrix_world.copy();rig.parent=root.parent;root.parent=rig;root.matrix_world=old
        for s in bpy.data.scenes:
            if root.name in s.objects:
                for camera in s.objects:
                    if camera.type=='CAMERA' and (camera==s.camera or camera.get('op_entry_camera')):
                        old=camera.matrix_world.copy();camera.parent=rig;camera.matrix_world=old
    original=cam.original
    if original.parent!=rig:
        old=original.matrix_world.copy();original.parent=rig;original.matrix_world=old
    # A 0.001-radius cell is shared by all nearby vertices, preserving local
    # coordinates while the camera moves within that cell.
    origin=Vector(tuple(round(float(x)/.001)*.001 for x in cp))
    for axis,value in zip('xyz',origin):root['op_anchor_'+axis]=value
    for i,(direction,mul,amplitude) in enumerate(nd.WAVES):
        d=tuple(nd.VectorUnit(direction));root['op_wave_phase'+str(i)]=(sum(float(origin[j])*d[j] for j in range(3))*math.tau*mul/root['biome_wave_length'])%math.tau
    rig.location=-(root.matrix_local@origin);root.update_tag();rig.update_tag()
    bpy.context.view_layer.update()
    return origin

def enable(scene,root):
    from .generator import upgrade_entry
    ensure(root);root['biome_enabled']=True;root['lod_enabled']=True;root['lod_max_depth']=24
    physical_scale(scene,root)
    root['lod_micro_normal']=.08
    if not root.animation_data or not any(f.data_path=='["biome_time"]' for f in root.animation_data.drivers):
        d=root.driver_add('["biome_time"]').driver;d.expression='frame/24'
    setup_world(scene,root)
    upgrade_entry(scene,root)

def setup_world(scene,root):
    if root.get('look_enabled'):
        from . import lookdev
        lookdev.environment(scene,root)
        return
    def orient(world):
        up=Vector(tuple(root.get('op_anchor_'+a,0.) for a in 'xyz'))
        up=(root.matrix_world.to_quaternion()@up).normalized() if up.length else Vector((0,0,1))
        east=Vector((0,0,1)).cross(up)
        east=east.normalized() if east.length>.00001 else Vector((1,0,0))
        north=up.cross(east)
        for axis,value in (('east',east),('north',north),('up',up)):
            world.node_tree.nodes['World sky '+axis].inputs[1].default_value=value
        world.node_tree.nodes['Interior photographic background'].inputs['Strength'].default_value=.7*root.get('op_sky_weight',root.get('op_inside_sky',0.))
        world.node_tree.update_tag();world.update_tag()
    if scene.world and scene.world.get('op_living_owner')==root.name and scene.world.get('op_sky_version')==6:
        orient(scene.world);return
    original=scene.world
    world=bpy.data.worlds.new(root.name+' Â· Physical environment');world.use_nodes=True
    world['op_living_owner']=root.name;world['op_sky_version']=6
    if original:world['op_previous_world']=original.name
    scene.world=world;world.node_tree.nodes.clear();g=nd.Graph(world.node_tree)
    path=Path(__file__).parent/'assets/ground/sky.hdr'
    if not path.exists():raise RuntimeError('The full add-on ZIP with CC0 sky data is required')
    env=g.node('ShaderNodeTexEnvironment','CC0 sky environment');env.image=bpy.data.images.load(str(path),check_existing=True)
    if not env.image.packed_file:env.image.pack()
    coord=g.node('ShaderNodeTexCoord').outputs['Generated']
    projections=[]
    for axis in ('east','north','up'):
        node=g.node('ShaderNodeVectorMath','World sky '+axis,operation='DOT_PRODUCT');g.put(coord,node.inputs[0]);projections.append(node.outputs['Value'])
    g.put(g.combine(*projections),env.inputs['Vector'])
    bg=g.node('ShaderNodeBackground');g.put(env.outputs['Color'],bg.inputs['Color']);bg.inputs['Strength'].default_value=.45
    sky=g.node('ShaderNodeBackground','Interior photographic background');g.put(env.outputs['Color'],sky.inputs['Color'])
    lp=g.node('ShaderNodeLightPath');mix=g.node('ShaderNodeMixShader');g.put(lp.outputs['Is Camera Ray'],mix.inputs[0])
    g.put(bg.outputs[0],mix.inputs[1]);g.put(sky.outputs[0],mix.inputs[2]);out=g.node('ShaderNodeOutputWorld');g.put(mix.outputs[0],out.inputs[0])
    orient(world)

def curves(obj):
    action=obj.animation_data.action if obj.animation_data else None
    if action:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves

def physical_scale(scene,root):
    """Preserve framing while leaving Blender's tiny clipping/shadow limits."""
    old=float(root['radius'])
    if old>=1000.:return
    factor=10000./old;center=root.matrix_world.translation.copy()
    cameras={s.camera for s in bpy.data.scenes if root.name in s.objects and s.camera}
    if root.op_lod.camera:cameras.add(root.op_lod.camera)
    for cam in cameras:
        local_center=cam.parent.matrix_world.inverted_safe()@center if cam.parent else center
        cam.location=local_center+(cam.location-local_center)*factor
        for fc in curves(cam):
            if fc.data_path!='location':continue
            c=local_center[fc.array_index]
            for point in fc.keyframe_points:
                point.co.y=c+(point.co.y-c)*factor
                point.handle_left.y=c+(point.handle_left.y-c)*factor;point.handle_right.y=c+(point.handle_right.y-c)*factor
        cam.data.ortho_scale*=factor;cam.data.clip_end*=factor
    for fc in curves(root):
        if fc.data_path=='["radius"]':
            for point in fc.keyframe_points:
                point.co.y*=factor;point.handle_left.y*=factor;point.handle_right.y*=factor
    root['radius']=10000.;root.id_properties_ui('radius').update(max=100000000.,soft_max=1000000.)
    root['op_precision_scale_from']=old;root.update_tag();bpy.context.view_layer.update()

def material(root,old=None,kind='TREE'):
    if old:
        result=old.copy();result.name=root.name+' Â· PBR '+old.name
        return result
    m,g=nd.material(root.name+' Â· Physical blade geometry')
    bsdf=g.node('ShaderNodeBsdfPrincipled','Physical blade surface')
    attribute=g.node('ShaderNodeVertexColor');attribute.layer_name='op_color'
    g.put(attribute.outputs['Color'],bsdf.inputs['Base Color']);bsdf.inputs['Roughness'].default_value=.68
    translucent=g.node('ShaderNodeBsdfTranslucent');g.put(attribute.outputs['Color'],translucent.inputs['Color'])
    blend=g.node('ShaderNodeMixShader');blend.inputs[0].default_value=.18
    g.put(bsdf.outputs[0],blend.inputs[1]);g.put(translucent.outputs[0],blend.inputs[2]);shader=blend.outputs[0]
    nd.output(g,shader);return m

def lighting(scene,root):
    """Explicit physical sun and soft sky fill work in Eevee and Cycles."""
    az=math.radians(root['sun_azimuth']);el=math.radians(root['sun_elevation'])
    sun=Vector((math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)))
    for name,direction,energy,color,shadow in (
        ('Sun',sun,3.0,(1.,.94,.84),True),
        ('Sky fill',Vector((-.3,.1,1.)).normalized(),.35,(.55,.72,1.),False),
        ('Horizon fill',Vector((.3,-.7,.4)).normalized(),.20,(.65,.78,1.),False)):
        ob=next((o for o in root.children if o.get('op_biome_light')==name),None)
        if ob is None:
            data=bpy.data.lights.new(root.name+' Â· '+name,'SUN');ob=bpy.data.objects.new(data.name,data)
            root.users_collection[0].objects.link(ob);ob.parent=root;ob['op_biome_light']=name
            if hasattr(ob,'light_linking'):ob.light_linking.receiver_collection=root.users_collection[0]
        ob.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();ob.data.energy=energy*root['exposure']
        ob.data.color=color;ob.data.use_shadow=shadow;ob.data.angle=.0093 if shadow else .5
        if shadow:
            ob.data.shadow_maximum_resolution=max(1e-8,root.get('op_shadow_resolution',root['radius']*root['biome_grass_height']*.08))
            ob.data.shadow_buffer_clip_start=max(1e-6,root['radius']*root['biome_grass_height']*.002)
            ob.data.use_shadow_jitter=True
            blockers=bpy.data.collections.get(root.get('op_shadow_collection',''))
            if blockers is None:
                blockers=bpy.data.collections.new(root.name+' Â· Local shadow casters');root['op_shadow_collection']=blockers.name
            for obj in root.children:
                if obj.get('op_role') in {'SURFACE','BIOME_INSTANCES'} and obj.name not in blockers.objects:blockers.objects.link(obj)
            ob.light_linking.blocker_collection=blockers
    surface=next(o for o in root.children if o.get('op_role')=='SURFACE')
    surface.visible_shadow=True;surface.visible_glossy=True;surface.visible_diffuse=True
    scene.eevee.use_raytracing=True
    scene.eevee.shadow_ray_count=4;scene.eevee.shadow_step_count=12
    if root.get('look_enabled'):
        from . import lookdev
        lookdev.lighting(scene,root)

def blades(name,collection,count):
    """Curved tapered ribbons: actual blade geometry, no flat grass image plane."""
    rng=random.Random(671);vertices=[];faces=[];colors=[]
    for i in range(count):
        angle=rng.random()*math.tau;rad=rng.random()**.6*.65;h=rng.uniform(.40,1.)
        x=math.cos(angle)*rad;y=math.sin(angle)*rad;lean=rng.uniform(.12,.65)
        width=rng.uniform(.018,.048);side=Vector((-math.sin(angle),math.cos(angle),0.))
        offset=len(vertices)
        for j in range(4):
            t=j/3.;center=Vector((x+math.cos(angle)*lean*t*t,y+math.sin(angle)*lean*t*t,h*t))
            w=width*(1.-t)**.65
            vertices.extend((tuple(center-side*w),tuple(center+side*w)))
        for j in range(3):faces.append((offset+2*j,offset+2*j+1,offset+2*j+3,offset+2*j+2))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    attr=mesh.color_attributes.new(name='op_color',type='FLOAT_COLOR',domain='CORNER')
    for poly in mesh.polygons:
        tone=rng.uniform(.65,1.2)
        for li in poly.loop_indices:
            z=mesh.vertices[mesh.loops[li].vertex_index].co.z
            attr.data[li].color=(tone*(.025+.07*z),tone*(.05+.14*z),tone*(.006+.022*z),1.)
    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);return obj

def assets(root):
    found={(o.get('op_asset_kind'),o.get('op_asset_lod')):o for o in root.children if o.get('op_role')=='BIOME_SOURCE'}
    realism=root.get('biome_realism',False)
    if realism and any(o.get('op_library_version',0)!=13 for key,o in found.items() if key[0]!='GRASS'):
        for key,ob in list(found.items()):
            if key[0]!='GRASS':bpy.data.objects.remove(ob,do_unlink=True);del found[key]
    kinds=('TREE','TREE_B','TREE_C','SAPLING','SAPLING_B','FIR','DEAD','GRASS','WILDGRASS','WILDGRASS_B','ROCK','FERN','FERN_B','FERN_C') if realism else ('TREE','TREE_B','TREE_C','GRASS','WILDGRASS','ROCK','FERN')
    required={(kind,level) for kind in kinds for level in range(3)}
    if required<=found.keys():
        if root.get('look_enabled'):
            from . import lookdev
            lookdev.wrap_assets(root)
        return found
    path=Path(__file__).parent/('assets/realism_library.blend' if realism else 'assets/biome_library.blend')
    if not path.exists():raise RuntimeError('Install the full add-on ZIP including its CC0 model library')
    present={kind for kind,level in found}
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):
        dst.objects=[n for n in src.objects if n.startswith('OP_') and n[3:].rsplit('_LOD',1)[0] not in present]
    collection=root.users_collection[0];mats={}
    for ob in dst.objects:
        collection.objects.link(ob);kind=ob['op_asset_kind'];level=ob['op_asset_lod']
        for i,old in enumerate(list(ob.data.materials)):
            if old:
                if old.name not in mats:mats[old.name]=material(root,old,kind)
                ob.data.materials[i]=mats[old.name]
        found[(kind,level)]=ob
    if 'GRASS' not in present:
        grassmat=material(root,kind='GRASS')
        for level,count in enumerate((56,18,6)):
            ob=blades(root.name+' Â· Grass source '+str(level),collection,count)
            ob['op_asset_kind']='GRASS';ob['op_asset_lod']=level;ob.data.materials.append(grassmat)
            ob.data.calc_loop_triangles();ob['op_triangles']=len(ob.data.loop_triangles);found[('GRASS',level)]=ob
    for (kind,level),ob in found.items():
        ob.name=root.name+' Â· '+kind+' source LOD'+str(level);ob.parent=root;ob.hide_render=True;ob.hide_set(True)
        ob.hide_select=True;ob['op_role']='BIOME_SOURCE';ob['op_owner']=root.name
    if root.get('look_enabled'):
        from . import lookdev
        lookdev.wrap_assets(root)
    return found

def sample(scene,root,directions,local=False):
    """Batch sample exact GN geometry AND climate weights, without a CPU noise copy."""
    surface=next(o for o in root.children if o.get('op_role')=='SURFACE')
    probe=next((o for o in root.children if o.get('op_probe_for')=='BIOME_BATCH'),None)
    if probe is None:
        mesh=bpy.data.meshes.new(root.name+' Â· Biome samples')
        probe=bpy.data.objects.new(mesh.name,mesh);root.users_collection[0].objects.link(probe);probe.parent=root
        probe.hide_select=True;probe['op_role']='LOD_PROBE';probe['op_probe_for']='BIOME_BATCH'
        mod=probe.modifiers.new('Exact shared biome sampler','NODES');mod.node_group=surface.modifiers[0].node_group
    origin=Vector(tuple(root.get('op_anchor_'+axis,0.) for axis in 'xyz'))
    probe.location=origin
    mesh=probe.data;mesh.clear_geometry();mesh.from_pydata([tuple(float(v[j])-float(origin[j]) for j in range(3)) for v in directions],[],[]);mesh.update()
    probe.modifiers[0].node_group=surface.modifiers[0].node_group
    dg=bpy.context.evaluated_depsgraph_get();dg.update();ev=probe.evaluated_get(dg).data
    canonical=ev.attributes.get('op_ground_position') if root.get('biome_realism') else None
    positions=[d.vector.copy() for d in canonical.data] if canonical else [v.co.copy() for v in ev.vertices]
    points=positions if local else [v+origin for v in positions]
    weights={k:[v.value for v in ev.attributes['op_'+k].data] if 'op_'+k in ev.attributes else [.5 if k=='cover' else 0.]*len(points) for k in ('land','forest','grass','desert','mountain','canyon','continent','cover')}
    return points,weights

def emitter(root,source):
    name=source['op_asset_kind']+str(source['op_asset_lod'])
    ob=next((o for o in root.children if o.get('op_scatter_key')==name),None)
    if ob:
        for node in ob.modifiers[0].node_group.nodes:
            if node.bl_idname=='GeometryNodeObjectInfo':node.inputs['Object'].default_value=source
        return ob
    mesh=bpy.data.meshes.new(root.name+' Â· '+name+' placements');ob=bpy.data.objects.new(mesh.name,mesh)
    root.users_collection[0].objects.link(ob);ob.parent=root;ob['op_role']='BIOME_INSTANCES';ob['op_scatter_key']=name
    ob['op_owner']=root.name;tree=bpy.data.node_groups.new(ob.name+' Â· Shared instances','GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    g=nd.Graph(tree);inp=g.node('NodeGroupInput');out=g.node('NodeGroupOutput');info=g.node('GeometryNodeObjectInfo',transform_space='ORIGINAL')
    info.inputs['Object'].default_value=source;inst=g.node('GeometryNodeInstanceOnPoints','Actual model instances')
    g.put(inp.outputs['Geometry'],inst.inputs['Points']);g.put(info.outputs['Geometry'],inst.inputs['Instance'])
    for name,key in (('Rotation','op_rotation'),('Scale','op_scale')):
        a=g.node('GeometryNodeInputNamedAttribute',data_type='FLOAT_VECTOR');a.inputs['Name'].default_value=key
        g.put(a.outputs['Attribute'],inst.inputs[name])
    g.put(inst.outputs['Instances'],out.inputs['Geometry']);mod=ob.modifiers.new('Open Planet Â· instanced geometry','NODES');mod.node_group=tree
    return ob

def lattice(center,spacing,radius,seed):
    """Jittered fixed cube-face cells; never reseeded as the camera moves."""
    radius=min(radius,spacing*65);count=max(2,math.ceil(2./spacing));step=2./count
    extent=math.ceil(radius/step*1.8)+2;extent=min(extent,100)
    x,y,z=center
    projections=((x,y,z),(-x,-y,z),(y,-x,z),(-y,x,z),(z,x,y),(-z,x,-y))
    result=[]
    for face,(den,u,v) in enumerate(projections):
        if den<=0.:continue
        u/=den;v/=den
        if abs(u)>1.+radius*3 or abs(v)>1.+radius*3:continue
        ix=int((u+1)/step);iy=int((v+1)/step)
        for a in range(max(0,ix-extent),min(count,ix+extent+1)):
            for b in range(max(0,iy-extent),min(count,iy+extent+1)):
                key=(a*73856093 ^ b*19349663 ^ face*83492791 ^ seed*2654435761)&0xffffffff
                rng=random.Random(key);uu=-1+(a+.02+rng.random()*.96)*step;vv=-1+(b+.02+rng.random()*.96)*step
                direction=lod_mesh.unit(lod_mesh.cube_key(face,uu,vv,1.))
                if (Vector(direction)-center).length<=radius:result.append((direction,key,rng.random()))
    return result

def update(scene,root,cam):
    ensure(root)
    if root.get('biome_enabled') and root.get('biome_realism'):
        from . import realism
        return realism.update(scene,root,cam)
    existing=[o for o in root.children if o.get('op_role')=='BIOME_INSTANCES']
    if not root.get('biome_enabled'):
        for ob in existing:ob.hide_render=True;ob.hide_viewport=True
        root['op_biome_triangles']=0;root['op_biome_instances']=0;return
    from .lod import logical_camera
    lighting(scene,root);sources=assets(root);cp,forward=logical_camera(root,cam)
    origin=cp.normalized();foot,_=sample(scene,root,[tuple(origin)]);alt=cp.length-foot[0].length
    maxrange=float(root['biome_range']);candidates=[]
    settings=(('TREE',root['biome_tree_height']*.45,maxrange),
              ('GRASS',root['biome_grass_height']*.40,min(maxrange,root['biome_grass_height']*600)),
              ('FERN',root['biome_fern_height']*2.8,min(maxrange,root['biome_fern_height']*180)),
              ('ROCK',root['biome_rock_size']*9.,min(maxrange,root['biome_rock_size']*180)))
    for kind,spacing,reach in settings:
        reach=min(reach,spacing*65.*(16. if kind=='GRASS' else 1.))
        if alt>reach*1.1:continue
        previous=0.
        for ring in ((1,2,4,8,16) if kind=='GRASS' else (1,)):
            radius=min(reach,spacing*65.*ring)
            for direction,key,prob in lattice(origin,spacing*ring,radius,int(root['seed'])*31+len(kind)+ring*173):
                delta=Vector(direction)*foot[0].length-cp;distance=delta.length
                if delta.dot(forward)<-spacing*ring*2 or distance<previous*.78:continue
                candidates.append((kind,direction,key,prob,radius,previous,ring))
            if radius>=reach:break
            previous=radius
    buckets=defaultdict(list);used=0;chosen=0;costs={}
    if candidates:
        points,weights=sample(scene,root,[tuple(c[1]) for c in candidates],local=True);ranked=[]
        surface=next(o for o in root.children if o.get('op_role')=='SURFACE')
        # Avoid subtracting rebased world matrices: their final float bits can
        # differ after visiting another camera, reshuffling capped placements.
        local_camera=cp-Vector(tuple(root.get('op_anchor_'+axis,0.) for axis in 'xyz'))
        bvh=BVHTree.FromObject(surface,bpy.context.evaluated_depsgraph_get())
        focal=scene.render.resolution_y/(2*math.tan(cam.data.angle_y*.5))
        for i,(kind,direction,key,prob,reach,previous,ring) in enumerate(candidates):
            land=weights['land'][i]
            if land<.98:continue
            forest=weights['forest'][i]
            patch=lod_mesh.smooth((weights['cover'][i]-.25)/.45)
            weight=(forest*lod_mesh.smooth((forest-.25)/.5)*(.35+.65*patch) if kind=='TREE' else
                max(weights['grass'][i],forest*.32)*(.75+.25*patch) if kind=='GRASS' else
                forest*.7*patch if kind=='FERN' else max(weights['desert'][i],weights['mountain'][i],.025))
            if prob>weight*root['biome_density']:continue
            distance=(points[i]-local_camera).length
            if distance>reach:continue
            size=root[{'TREE':'biome_tree_height','GRASS':'biome_grass_height','FERN':'biome_fern_height','ROCK':'biome_rock_size'}[kind]]
            rng=random.Random(key);size*=rng.uniform(.45 if kind=='TREE' else .72,1.32)
            size*=1.-lod_mesh.smooth((distance/reach-.75)/.25)
            if previous:size*=lod_mesh.smooth((distance/previous-.78)/.22)
            pixels=size*focal/max(distance,1e-10)
            if pixels<.65:continue
            actualkind='WILDGRASS' if kind=='GRASS' and key%4!=0 else kind
            if kind=='TREE':actualkind=('TREE','TREE_B','TREE_C')[key%3]
            level=0 if pixels>350 else 1 if pixels>30 else 2
            ranked.append((pixels,i,actualkind,level,size,key))
        ranked.sort(reverse=True)
        # Reserve ground-cover capacity when trees are visible. A nearby pine
        # must not consume the entire budget and leave an empty forest floor.
        tree_limit=root['biome_budget']*(.65 if any(v[2] in {'GRASS','WILDGRASS','FERN'} for v in ranked) else 1.)
        tree_used=0;tree_levels=[0,0,0];tree_limits=[tree_limit*.5,tree_limit*.25,tree_limit]
        for pixels,i,kind,level,size,key in ranked:
            if chosen>=int(root['biome_instances']):break
            # If a nearby high model exhausts the cap, progressively simplify it.
            while level<3:
                cost=sources[(kind,level)]['op_triangles']
                if used+cost<=root['biome_budget'] and (not kind.startswith('TREE') or (tree_used+cost<=tree_limit and tree_levels[level]+cost<=tree_limits[level])):break
                level+=1
            if level==3:continue
            cost=sources[(kind,level)]['op_triangles']
            direction=Vector(candidates[i][1])
            hit,normal,index,travel=bvh.ray_cast(points[i]+direction*.002,-direction,.004)
            if hit is None:continue
            used+=cost;chosen+=1
            if kind.startswith('TREE'):tree_used+=cost;tree_levels[level]+=cost
            axis=direction if kind.startswith('TREE') else normal.normalized()
            q=Vector((0,0,1)).rotation_difference(axis)@Quaternion((0,0,1),(key%65536)/65536*math.tau)
            point=hit-axis*size*(.035 if kind.startswith('TREE') else .05)
            patch_scale=candidates[i][6] if kind in {'GRASS','WILDGRASS'} else 1.
            aspect=random.Random(key+19).uniform(.70,1.15) if kind.startswith('TREE') else 1.
            buckets[(kind,level)].append((tuple(point),tuple(q.to_euler()),(size*patch_scale*aspect,size*patch_scale*aspect,size),key if key<2147483648 else key-4294967296))
    for key,source in sources.items():
        data=buckets[key];ob=emitter(root,source);ob.hide_render=not data;ob.hide_viewport=not data
        anchor=Vector(tuple(root.get('op_anchor_'+axis,0.) for axis in 'xyz'));ob.location=anchor
        mesh=ob.data;mesh.clear_geometry();mesh.from_pydata([v[0] for v in data],[],[])
        for name,column in (('op_rotation',1),('op_scale',2)):
            a=mesh.attributes.get(name) or mesh.attributes.new(name=name,type='FLOAT_VECTOR',domain='POINT')
            if data:a.data.foreach_set('vector',[x for row in data for x in row[column]])
        ids=mesh.attributes.get('id') or mesh.attributes.new(name='id',type='INT',domain='POINT')
        if data:ids.data.foreach_set('value',[row[3] for row in data])
        mesh.update();ob['op_instance_count']=len(data);ob['op_expanded_triangles']=len(data)*source['op_triangles']
    root['op_biome_triangles']=used;root['op_biome_instances']=chosen
    root['op_biome_status']=f'{chosen:,} instances Â· {used:,} expanded triangles'
    lighting(scene,root)
