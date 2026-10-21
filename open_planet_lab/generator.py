# SPDX-License-Identifier: GPL-3.0-or-later
import math
import bpy
from mathutils import Vector
from . import nodes as nd
from .presets import BASE, PRESETS, RANGES, LABELS

def prop_driver(obj,path,index,root,key,expr='v'):
    d=obj.driver_add(path,index).driver;d.expression=expr
    v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=root;v.targets[0].data_path='["%s"]'%key

def mesh_obj(name,collection,verts,faces):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);collection.objects.link(ob)
    for f in mesh.polygons:f.use_smooth=True
    return ob

def sphere(name,collection,segments=192,rings=96):
    # Explicit topology avoids context-dependent operators and coincident poles.
    vs=[(0.,0.,1.)]
    for j in range(1,rings):
        th=math.pi*j/rings;st=math.sin(th);ct=math.cos(th)
        vs.extend((st*math.cos(math.tau*i/segments),st*math.sin(math.tau*i/segments),ct) for i in range(segments))
    bottom=len(vs);vs.append((0.,0.,-1.));fs=[]
    for i in range(segments):fs.append((0,1+i,1+(i+1)%segments))
    for j in range(rings-2):
        a=1+j*segments;b=a+segments
        fs.extend((a+i,b+i,b+(i+1)%segments,a+(i+1)%segments) for i in range(segments))
    a=bottom-segments
    for i in range(segments):fs.append((a+i,bottom,a+(i+1)%segments))
    return mesh_obj(name,collection,vs,fs)

def geometry(ob,root,layer,kind):
    canopy_offset=0.
    t=bpy.data.node_groups.new(ob.name+' Â· Geometry','GeometryNodeTree')
    t.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    t.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    g=nd.Graph(t);inp=g.node('NodeGroupInput');out=g.node('NodeGroupOutput');p=nd.params(g,None,root)
    pos=g.node('GeometryNodeInputPosition').outputs[0]
    origin=nd.anchor(g,root) if layer=='SURFACE' and kind=='ROCK' else None
    v=g.vec('NORMALIZE',g.vec('ADD',pos,origin) if origin is not None else pos)
    field=nd.terrain_field(g,v,p)
    if layer=='SURFACE':
        dry=g.math('MAXIMUM',g.math('SUBTRACT',field,g.math('MAXIMUM',p['sea_level'],.45)),0.)
        height=g.math('MULTIPLY',dry,p['relief'])
        cr=g.node('ShaderNodeTexVoronoi','Crater basins',distance='EUCLIDEAN',feature='F1')
        g.put(v,cr.inputs['Vector']);g.put(p['crater_scale'],cr.inputs['Scale']);cr.inputs['Randomness'].default_value=1.
        d=cr.outputs['Distance'];bowl=g.math('MULTIPLY',g.math('SUBTRACT',1.,g.smooth(d,.08,.34)),-.025)
        rim=g.math('MULTIPLY',g.math('MULTIPLY',g.smooth(d,.24,.32),g.math('SUBTRACT',1.,g.smooth(d,.32,.43))),.012)
        height=g.math('ADD',height,g.math('MULTIPLY',g.math('ADD',bowl,rim),p['crater_amount']))
        if kind in {'GAS','STAR'}:height=g.math('MULTIPLY',g.math('SUBTRACT',field,.5),p['relief'])
        if kind in {'ROCK','BROKEN'}:
            camera=g.node('GeometryNodeObjectInfo','LOD Camera',transform_space='RELATIVE')
            camera.inputs['Object'].default_value=root.op_lod.camera or bpy.context.scene.camera
            distance=g.vec('DISTANCE',pos,camera.outputs['Location'])
            fade=nd.distance_fade(g,p,distance)
            height=g.math('ADD',height,nd.micro_height(g,v,p,fade))
        if kind=='ROCK':
            biome=nd.biome_fields(g,v,p)
            height=g.math('ADD',g.math('MULTIPLY',height,g.math('SUBTRACT',1.,p['biome_enabled'])),
                          g.math('MULTIPLY',biome['height'],p['biome_enabled']))
            # Measure ecology fades from the displaced ground. Measuring from
            # the undeformed sphere mistakes continental elevation for camera
            # altitude and leaves a distant canopy proxy beneath nearby trees.
            living_position=g.vec('ADD',pos,g.vec('SCALE',v,scale=biome['height']))
            distance=g.vec('DISTANCE',living_position,camera.outputs['Location'])
            # Far woodland becomes a bounded geometric canopy proxy. Local
            # instances take over as the camera enters that same area.
            reach=g.math('MINIMUM',p['biome_range'],p['biome_tree_distance'] if root.get('biome_realism') else g.math('MULTIPLY',p['biome_tree_height'],.45*65.))
            canopyfade=g.smooth(distance,g.math('MULTIPLY',reach,g.math('SUBTRACT',1.,p['biome_transition'])),reach)
            if root.get('biome_realism'):
                from . import ecology
                canopy,_=ecology.graph_canopy(g,v,p,biome['forest'])
                resolution=g.node('GeometryNodeInputNamedAttribute',data_type='FLOAT');resolution.inputs['Name'].default_value='op_mesh_spacing'
                resolved=g.math('SUBTRACT',1.,g.smooth(resolution.outputs['Attribute'],g.math('MULTIPLY',p['biome_tree_height'],.18),g.math('MULTIPLY',p['biome_tree_height'],.65)))
                canopy_offset=g.math('MULTIPLY',g.math('MULTIPLY',g.math('MULTIPLY',canopy,canopyfade),resolved),p['biome_enabled'])
            else:
                canopy=g.noise(v,g.math('MULTIPLY',3000.,100.),2.,.6,0.,p['seed'])
                canopy=g.math('MULTIPLY',g.math('MULTIPLY',canopy,biome['forest']),g.math('MULTIPLY',p['biome_tree_height'],canopyfade))
                height=g.math('ADD',height,g.math('MULTIPLY',canopy,p['biome_enabled']))
            # Sub-centimetre soil relief and distant turf are mesh displacement;
            # the finer photographed grain remains in the material.
            soil=g.math('MULTIPLY',g.math('SUBTRACT',g.noise(pos,g.math('MULTIPLY',3000.,1000.),3.,.65,0.,p['seed']),.5),.000000012)
            turf=g.math('MULTIPLY',g.noise(pos,g.math('MULTIPLY',1000.,1000.),2.,.65,0.,p['seed']),g.math('MULTIPLY',biome['grass'],g.math('MULTIPLY',p['biome_grass_height'],.28)))
            height=g.math('ADD',height,g.math('MULTIPLY',p['biome_enabled'],g.math('MULTIPLY',biome['land'],g.math('ADD',soil,turf))))
    else:
        f=g.noise(v,p['cloud_scale'],5.,.7,1.7,p['seed'])
        height=g.math('ADD',p['cloud_height'],g.math('MULTIPLY',f,p['cloud_depth']))
    setpos=g.node('GeometryNodeSetPosition','Actual displaced mesh')
    geo=inp.outputs['Geometry']
    if layer=='SURFACE' and kind=='ROCK':
        for key in ('land','forest','grass','desert','mountain','height','canyon','continent','cover'):
            store=g.node('GeometryNodeStoreNamedAttribute','World biome '+key,data_type='FLOAT',domain='POINT')
            store.inputs['Name'].default_value='op_'+key
            g.put(geo,store.inputs['Geometry']);g.put(biome[key],store.inputs['Value']);geo=store.outputs['Geometry']
    if kind=='BROKEN' and layer=='SURFACE':
        cr=g.node('ShaderNodeTexVoronoi','Broken crust',feature='DISTANCE_TO_EDGE');g.put(v,cr.inputs['Vector']);cr.inputs['Scale'].default_value=3.8
        delete=g.node('GeometryNodeDeleteGeometry','Open fracture seams',domain='FACE');g.put(geo,delete.inputs['Geometry']);g.put(g.math('LESS_THAN',cr.outputs['Distance'],.035),delete.inputs['Selection']);geo=delete.outputs[0]
        cells=g.node('ShaderNodeTexVoronoi','Fracture plate displacement',feature='F1');g.put(v,cells.inputs['Vector']);cells.inputs['Scale'].default_value=3.8
        plate=g.noise(cells.outputs['Position'],4.,0.,.5,0.,p['seed'])
        height=g.math('ADD',height,g.math('MULTIPLY',plate,.3))
        cap=g.math('GREATER_THAN',g.vec('DOT_PRODUCT',v,(.72,-.64,.27)),.83)
        wedge=g.node('GeometryNodeDeleteGeometry','Missing crust sector',domain='FACE');g.put(geo,wedge.inputs[0]);g.put(cap,wedge.inputs['Selection']);geo=wedge.outputs[0]
    offset=g.vec('SCALE',v,scale=height)
    if layer=='SURFACE' and kind=='ROCK':
        wave=g.vec('SCALE',nd.wave_offset(g,v,p,biome,pos,root),scale=p['biome_enabled'])
        offset=g.vec('ADD',offset,wave)
        store=g.node('GeometryNodeStoreNamedAttribute','Geometric ocean displacement',data_type='FLOAT_VECTOR',domain='POINT')
        store.inputs['Name'].default_value='op_wave_offset';g.put(geo,store.inputs['Geometry']);g.put(wave,store.inputs['Value']);geo=store.outputs['Geometry']
        if root.get('biome_realism'):
            store=g.node('GeometryNodeStoreNamedAttribute','Canonical ground without distant crowns',data_type='FLOAT_VECTOR',domain='POINT')
            store.inputs['Name'].default_value='op_ground_position';g.put(geo,store.inputs['Geometry']);g.put(g.vec('ADD',pos,offset),store.inputs['Value']);geo=store.outputs['Geometry']
            offset=g.vec('ADD',offset,g.vec('SCALE',v,scale=canopy_offset))
    g.put(geo,setpos.inputs['Geometry'])
    if origin is not None:
        # Rebased output avoids adding metre-scale displacement to a unit-radius
        # float: subtract the anchor BEFORE adding local relief and waves.
        g.put(g.vec('ADD',pos,offset),setpos.inputs['Position'])
    else:g.put(offset,setpos.inputs['Offset'])
    g.put(setpos.outputs[0],out.inputs[0])
    mod=ob.modifiers.new('Open Planet Â· real geometry','NODES');mod.node_group=t

def ring_mesh(name,collection):
    vs=[];fs=[];segments=512
    for r in (1.,5.1):
        vs.extend((r*math.cos(math.tau*i/segments),r*math.sin(math.tau*i/segments),0.) for i in range(segments))
    fs.extend((i,(i+1)%segments,segments+(i+1)%segments,segments+i) for i in range(segments))
    return mesh_obj(name,collection,vs,fs)

def create_planet(scene,preset='TERRA',quality=192,location=(0,0,0),name=None):
    label,kind,overrides=PRESETS[preset]
    collection=bpy.data.collections.new(name or label);scene.collection.children.link(collection)
    root=bpy.data.objects.new(name or label,None);collection.objects.link(root);root.location=location
    root.empty_display_type='SPHERE';root.empty_display_size=.15
    root['op_root']=True;root['op_kind']=kind;root['op_preset']=preset;root['op_quality']=quality
    for k,v in {**BASE,**overrides}.items():
        root[k]=v
        if k.endswith('_color'):root.id_properties_ui(k).update(subtype='COLOR',min=0.,max=1.)
        elif not isinstance(v,bool):
            lo,hi=RANGES[k];root.id_properties_ui(k).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description=LABELS[k])
    for i in range(3):prop_driver(root,'scale',i,root,'radius')
    from . import lod
    lod.ensure(root)
    t=nd.controls(root);root['op_controls']=t.name
    surface=sphere(root.name+' Â· Terrain',collection,quality,quality//2);surface.parent=root
    surface['op_role']='SURFACE';surface.data.materials.append(nd.surface(root,t,kind));geometry(surface,root,'SURFACE',kind)
    if kind=='BROKEN':
        core=sphere(root.name+' Â· Exposed core',collection,128,64);core.parent=root;core.scale=(.84,.84,.84)
        core.data.materials.append(nd.core(root,t));core['op_owner']=root.name;core['op_role']='CORE'
    cloud=sphere(root.name+' Â· Clouds',collection,max(128,quality//2),max(64,quality//4));cloud.parent=root
    cloud['op_role']='CLOUDS';cloud.data.materials.append(nd.clouds(root,t));geometry(cloud,root,'CLOUDS',kind)
    atmo=sphere(root.name+' Â· Atmosphere',collection,192,96);atmo.parent=root;atmo['op_role']='ATMOSPHERE'
    for i in range(3):prop_driver(atmo,'scale',i,root,'atmosphere_height','1+v')
    atmo.data.materials.append(nd.atmosphere(root,t,kind))
    ring=ring_mesh(root.name+' Â· Rings',collection);ring.parent=root;ring['op_role']='RINGS'
    prop_driver(ring,'rotation_euler',0,root,'ring_tilt','v*0.0174532925199433')
    ring.data.materials.append(nd.rings(root,t))
    # Each full system is appendable and can be dragged from the Asset Browser.
    collection.asset_mark();collection.asset_data.description='Open Planet Designer Â· '+label+' Â· shared Eevee/Cycles shaders and actual geometry'
    for ob in (surface,cloud,atmo,ring):
        ob['op_owner']=root.name
        if hasattr(ob,'visible_shadow'):ob.visible_shadow=False
        if hasattr(ob,'visible_diffuse'):ob.visible_diffuse=False
        if hasattr(ob,'visible_glossy'):ob.visible_glossy=False
    bpy.context.view_layer.objects.active=surface
    for o in bpy.context.selected_objects:o.select_set(False)
    surface.select_set(True)
    return root

def upgrade_entry(scene,root,refresh=True):
    """Upgrade an existing world without replacing its controller or animation."""
    from . import lod
    for k,v in BASE.items():
        if k not in root:root[k]=v
    lod.ensure(root)
    for ob in list(root.children):
        if ob.get('op_role')=='LOD_PROBE':
            mesh=ob.data;bpy.data.objects.remove(ob,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)
    t=nd.controls(root);root['op_controls']=t.name;kind=root['op_kind']
    for ob in root.children:
        role=ob.get('op_role')
        if role not in {'SURFACE','CLOUDS','ATMOSPHERE','RINGS','CORE'}:continue
        old_mats=list(ob.data.materials);ob.data.materials.clear()
        maker={'SURFACE':lambda:nd.surface(root,t,kind),'CLOUDS':lambda:nd.clouds(root,t),
               'ATMOSPHERE':lambda:nd.atmosphere(root,t,kind),'RINGS':lambda:nd.rings(root,t),'CORE':lambda:nd.core(root,t)}
        ob.data.materials.append(maker[role]())
        for m in old_mats:
            if m.users==0:bpy.data.materials.remove(m)
        if role in {'SURFACE','CLOUDS'}:
            for mod in list(ob.modifiers):
                if mod.type=='NODES' and mod.name.startswith('Open Planet'):
                    old=mod.node_group;ob.modifiers.remove(mod)
                    if old.users==0:bpy.data.node_groups.remove(old)
            geometry(ob,root,role,kind)
    root['lod_enabled']=True;root.update_tag();scene.render.use_lock_interface=True
    if refresh:lod.update(scene,root,True)

def create_entry_demo():
    from . import lod
    scene=bpy.data.scenes.new('OP Â· Atmospheric Entry');bpy.context.window.scene=scene;configure(scene,1280,720)
    cam=camera(scene);cam.data.type='PERSP';cam.data.lens=28.;cam.data.clip_start=.000001;cam.data.clip_end=30.
    root=create_planet(scene,'TERRA',128,name='Terra Â· Camera Adaptive Entry')
    root['relief']=.008;root['atmosphere_height']=.0157;root['cloud_height']=.0016;root['cloud_depth']=.0005
    root['cloud_coverage']=.46;root['ice']=.94;root['lod_near']=.0015;root['lod_far']=.035
    root['lod_micro_height']=.00010;root['lod_budget']=60000;root['lod_max_depth']=20;root['lod_enabled']=True
    root.op_lod.camera=cam;root.update_tag();bpy.context.view_layer.update()
    surface=next(o for o in root.children if o.get('op_role')=='SURFACE')
    # Pick an inland descent target, rather than ending over featureless ocean.
    candidates=[]
    for x in (-.50,-.25,0.,.25,.50):
        for z in (.10,.30,.50,.65):
            candidate=Vector((x,-math.sqrt(max(.01,1-x*x-z*z)),z)).normalized()
            h=lod.sample_radius(scene,root,surface,candidate)
            candidates.append((abs(h-1.001),candidate,h))
    _,direction,_=min(candidates,key=lambda v:v[0]);tangent=(Vector((0,0,1))-direction*direction.z).normalized()
    height=lod.sample_radius(scene,root,surface,direction)
    path=[]
    for frame,alt in ((1,3.),(55,.10),(100,.025),(145,.007),(190,.0014),(240,.000035)):
        cam.location=direction*root['radius']*(height+alt)
        for _ in range(3):
            bpy.context.view_layer.update()
            localheight=lod.sample_radius(scene,root,surface,direction)
            cam.location=direction*root['radius']*(localheight+alt)
        blend=1.-min(1.,alt/.10)
        ray=(-direction*(1.-blend*.70)+tangent*blend*.85).normalized()
        cam.rotation_euler=ray.to_track_quat('-Z','Y').to_euler()
        path.append((frame,cam.location.copy(),cam.rotation_euler.copy()))
    for frame,location,rotation in path:
        cam.location=location;cam.rotation_euler=rotation
        cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_euler',frame=frame)
    # Linear segments are predictable when scrubbing; the terrain response itself
    # remains continuously distance-faded between the near and far controls.
    if cam.animation_data and cam.animation_data.action:
        for layer in cam.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(1);scene.render.use_lock_interface=True;lod.update(scene,root,True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='RENDERED';area.spaces.active.overlay.show_overlays=False
    return scene,root

def look_at(ob,target):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()

def configure(scene,width=1000,height=1000):
    scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
    scene.world=bpy.data.worlds.new(scene.name+' Â· Space');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(0,0,0,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    scene.cycles.samples=256;scene.cycles.use_denoising=False;scene.cycles.use_adaptive_sampling=False
    if hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'):scene.eevee.taa_render_samples=256
    scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=24
    scene.render.fps=24;scene.frame_end=240
    scene['op_note']='Open Planet Designer | engine consistency uses analytic sunlight and shell atmosphere; see README.md'
    # No engine-specific compositor effects. Glow can be added downstream by the artist.
    return scene

def camera(scene,location=(0,-10.,3.),target=(0,0,0),ortho=5.7):
    data=bpy.data.cameras.new('OP Camera');ob=bpy.data.objects.new('OP Camera',data);scene.collection.objects.link(ob)
    ob.location=location;look_at(ob,target);data.type='ORTHO';data.ortho_scale=ortho;data.lens=50.;scene.camera=ob
    return ob

def create_demo():
    scene=bpy.data.scenes.new('Open Planet Â· Terra');bpy.context.window.scene=scene;configure(scene,1100,1100)
    root=create_planet(scene,'TERRA',256);camera(scene,(0,-10,2.5),ortho=5.35)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
    return scene,root

def active_root(context):
    ob=context.object
    while ob:
        if ob.get('op_root'):return ob
        ob=ob.parent
    return None
