# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded adaptive geometry updates for viewport, scrubbing, and final renders."""
import math
import time
import bpy
from bpy.app.handlers import persistent
from mathutils import Vector
from . import lod_mesh
from .presets import BASE

DEFAULTS=dict(lod_enabled=False,lod_auto=True,lod_budget=60000,lod_pixels=4.,
    lod_near=.004,lod_far=.25,lod_max_depth=18,lod_micro_height=.00010,
    lod_micro_scale=1800.,lod_micro_normal=.35,lod_ao=.18,lod_fit_clip=True)
_cache={};_busy=False;_pending=set();_loaded=set()

def ensure(root):
    from .presets import LABELS,RANGES
    for key,value in DEFAULTS.items():
        if key not in root:root[key]=value
        lo,hi=RANGES.get(key,(0,1))
        if isinstance(value,bool):root.id_properties_ui(key).update(description=LABELS.get(key,key))
        else:root.id_properties_ui(key).update(min=lo,max=hi,soft_min=lo,soft_max=hi,description=LABELS.get(key,key))

def camera_for(scene,root):
    return root.op_lod.camera or scene.camera

def logical_camera(root,cam):
    # Shared-parent local matrices are invariant under the floating-origin
    # translation. World-matrix subtraction can change the last bits when a
    # distant camera is revisited, which would reshuffle borderline LOD cells.
    if root.parent and root.parent==cam.original.parent:
        relative=root.matrix_local.inverted_safe()@cam.matrix_local
    else:relative=root.matrix_world.inverted_safe()@cam.matrix_world
    return relative.translation, (relative.to_3x3()@Vector((0,0,-1))).normalized()

def assign_mesh(ob,verts,faces):
    mesh=ob.data
    if mesh.users>1:mesh=mesh.copy();ob.data=mesh
    mesh.clear_geometry();mesh.from_pydata(verts,[],faces);mesh.update()
    for p in mesh.polygons:p.use_smooth=True
    if ob.parent and ob.parent.get('biome_realism'):
        import numpy as np
        points=np.asarray(verts,dtype=np.float32)
        edges=np.empty(len(mesh.edges)*2,dtype=np.int32);mesh.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
        spacing=np.zeros(len(verts),dtype=np.float32)
        if len(edges):
            lengths=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1)
            np.maximum.at(spacing,edges[:,0],lengths);np.maximum.at(spacing,edges[:,1],lengths)
        attr=mesh.attributes.get('op_mesh_spacing') or mesh.attributes.new(name='op_mesh_spacing',type='FLOAT',domain='POINT')
        if len(spacing):attr.data.foreach_set('value',spacing)

def split_living_surface(root,surface,verts,faces,cp,origin):
    """Bound the shadow-casting patch independently of the complete far globe."""
    far=next((o for o in root.children if o.get('op_role')=='FAR_SURFACE'),None)
    if far is None:
        mesh=bpy.data.meshes.new(root.name+' Â· Distant terrain');far=bpy.data.objects.new(mesh.name,mesh)
        root.users_collection[0].objects.link(far);far.parent=root;far['op_role']='FAR_SURFACE';far['op_owner']=root.name
        far.modifiers.new('Open Planet Â· distant terrain','NODES')
    far.hide_render=False;far.hide_viewport=False;far.location=origin;surface.location=origin
    far.modifiers[0].node_group=surface.modifiers[0].node_group
    if list(far.data.materials)!=list(surface.data.materials):
        far.data.materials.clear()
        for mat in surface.data.materials:far.data.materials.append(mat)
    far.visible_shadow=False
    reach=root.get('biome_shadow_distance',.004)*1.5
    foot=cp.normalized()
    close=[sum((v[j]-foot[j])**2 for j in range(3))<reach*reach for v in verts]
    near_faces=[];far_faces=[]
    for face in faces:(near_faces if all(close[i] for i in face) else far_faces).append(face)
    for ob,subset in ((surface,near_faces),(far,far_faces)):
        used=sorted({i for face in subset for i in face});remap={v:i for i,v in enumerate(used)}
        points=[tuple(verts[i][j]-float(origin[j]) for j in range(3)) for i in used]
        assign_mesh(ob,points,[tuple(remap[i] for i in face) for face in subset])
    root['op_near_terrain_triangles']=len(near_faces);root['op_far_terrain_triangles']=len(far_faces)

def sample_radius(scene,root,source,cp):
    """Evaluate the SAME displacement graph at the camera's radial footpoint.

    A one-vertex service mesh has no renderable faces. This avoids an inaccurate
    CPU copy of Blender's shader noise when estimating local camera altitude.
    """
    probe=next((o for o in root.children if o.get('op_probe_for')==source.name),None)
    if probe is None:
        mesh=bpy.data.meshes.new(root.name+' Â· LOD height sample');mesh.from_pydata([(0,0,1)],[],[])
        probe=bpy.data.objects.new(mesh.name,mesh);root.users_collection[0].objects.link(probe);probe.parent=root
        probe.hide_select=True;probe['op_role']='LOD_PROBE';probe['op_probe_for']=source.name
        mod=probe.modifiers.new('Exact terrain height sample','NODES');mod.node_group=source.modifiers[0].node_group
    direction=cp.normalized() if cp.length>1e-8 else Vector((0,0,1))
    origin=Vector(tuple(root.get('op_anchor_'+axis,0.) for axis in 'xyz')) if source.get('op_role')=='SURFACE' else Vector()
    probe.location=origin;probe.data.vertices[0].co=direction-origin;probe.data.update()
    dg=bpy.context.evaluated_depsgraph_get();dg.update();ev=probe.evaluated_get(dg)
    return (ev.data.vertices[0].co+origin).length if len(ev.data.vertices) else 1.

def signature(scene,root,cam):
    # Avoid a feedback rebuild when our own mesh update triggers the depsgraph.
    return (cam.original.as_pointer(),tuple(round(v,10) for row in root.matrix_world for v in row),
            tuple(round(v,10) for row in cam.matrix_world for v in row),cam.data.type,cam.data.lens,cam.data.ortho_scale,
            scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage,
            tuple(root.get(k,v) for k,v in DEFAULTS.items()),root.get('cloud_coverage',0),root.get('cloud_height',0),
            root.get('cloud_depth',0),root.get('atmosphere',0),root.get('rings',0),root.get('seed',0),
            root.get('relief',0),root.get('sea_level',0),root.get('crater_amount',0),root.get('crater_scale',0),
            tuple((k,root.get(k,v)) for k,v in BASE.items() if (k.startswith('biome_') or k.startswith('look_')) and k!='biome_time'))

def update(scene,root,force=False):
    global _busy
    if _busy or not root.get('lod_enabled'):return
    cam=camera_for(scene,root)
    if not cam or cam.type!='CAMERA':root['op_lod_status']='Choose a camera';return
    if root.mode!='OBJECT' or any(o.mode!='OBJECT' for o in root.children if o.type=='MESH'):return
    dg=bpy.context.evaluated_depsgraph_get();ecam=cam.evaluated_get(dg)
    sig=signature(scene,root,ecam);key=(scene.as_pointer(),root.as_pointer())
    if not force and _cache.get(key)==sig:return
    _busy=True;t=time.perf_counter()
    try:
        cp,forward=logical_camera(root,ecam)
        origin=Vector()
        if root.get('biome_enabled'):
            from . import biome
            origin=biome.rebase(scene,root,cam,cp)
            dg=bpy.context.evaluated_depsgraph_get();dg.update();ecam=cam.evaluated_get(dg)
        budget=max(2048,int(root['lod_budget']));r=max(.0001,float(root['radius']))
        h=scene.render.resolution_y*scene.render.resolution_percentage/100
        focal=h/max(2*math.tan(ecam.data.angle_y*.5),1e-6)
        root['op_focal_pixels']=focal
        common=dict(focal=focal,pixels=root['lod_pixels'],near=root['lod_near'],far=root['lod_far'],
            max_depth=int(root['lod_max_depth']),forward=tuple(forward))
        if root.get('lod_fit_clip',True):
            cam.data.clip_start=max(.000001,r*.000000001)
            cam.data.clip_end=max(r*(cp.length+2.),r*3.)
        if ecam.data.type=='ORTHO':common.update(ortho_size=ecam.data.ortho_scale/r,focal=h)
        by_role={o.get('op_role'):o for o in root.children if o.type=='MESH'}
        inside_sky=bool(root.get('biome_enabled') and root['atmosphere'] and cp.length<1.+root['atmosphere_height'])
        if root.get('biome_enabled'):
            root['op_inside_sky']=float(inside_sky);root.update_tag()
            # Ease the photographed sky into the atmosphere. Switching from
            # black orbital space to a full daylight sky at the shell boundary
            # makes an entry shot visibly pop in a single frame.
            sky_weight=1.-lod_mesh.smooth((cp.length-1.-.0015)/max(.0001,root['atmosphere_height']-.0015))
            root['op_sky_weight']=sky_weight if root['atmosphere'] else 0.
            root['op_living_cloud_visibility']=1.-sky_weight
            from . import biome
            biome.setup_world(scene,root)
        for ob in root.children:
            for mod in ob.modifiers:
                if mod.type=='NODES' and mod.node_group:
                    node=mod.node_group.nodes.get('LOD Camera')
                    if node and node.inputs['Object'].default_value!=cam:node.inputs['Object'].default_value=cam
        fixed=0
        if 'ATMOSPHERE' in by_role:
            ob=by_role['ATMOSPHERE'];ob.hide_render=not root['atmosphere'] or inside_sky;ob.hide_viewport=ob.hide_render
            seg=max(16,min(96,int(math.sqrt(budget*.09))//4*4))
            if ob.get('op_lod_segments')!=seg:
                from .generator import sphere
                temp=sphere('OP temporary atmosphere',root.users_collection[0],seg,seg//2)
                old=ob.data
                for mat in old.materials:temp.data.materials.append(mat)
                ob.data=temp.data;bpy.data.objects.remove(temp,do_unlink=True)
                if old.users==0:bpy.data.meshes.remove(old)
                ob['op_lod_segments']=seg
            if not ob.hide_render:fixed+=len(ob.data.polygons)*2
        if 'RINGS' in by_role:
            ob=by_role['RINGS'];ob.hide_render=root['rings']<=0;ob.hide_viewport=ob.hide_render
            if not ob.hide_render:fixed+=len(ob.data.polygons)*2
        if 'CORE' in by_role:
            ob=by_role['CORE'];seg=max(16,min(128,int(math.sqrt(budget*.10))//4*4))
            if ob.get('op_lod_segments')!=seg:
                from .generator import sphere
                temp=sphere('OP temporary core',root.users_collection[0],seg,seg//2);old=ob.data
                for mat in old.materials:temp.data.materials.append(mat)
                ob.data=temp.data;bpy.data.objects.remove(temp,do_unlink=True)
                if old.users==0:bpy.data.meshes.remove(old)
                ob['op_lod_segments']=seg
            fixed+=len(ob.data.polygons)*2
        # Interior photographic sky already includes clouds. The distant
        # procedural shell is for orbital views; rendering its inside faces
        # over that sky causes EEVEE/Cycles transparency-order differences.
        clouds=by_role.get('CLOUDS')
        under_clouds=bool(root.get('biome_enabled') and cp.length<1.+root['cloud_height']+root['cloud_depth'])
        cloud_budget=int(budget*.22) if clouds and root['cloud_coverage']>0 and not under_clouds else 0
        if clouds:
            clouds.hide_render=cloud_budget==0;clouds.hide_viewport=cloud_budget==0
        remaining=max(48,budget-fixed-cloud_budget)
        local_radius=sample_radius(scene,root,by_role['SURFACE'],cp)
        if root.get('look_enabled'):
            from . import lookdev
            lookdev.environment(scene,root,local_radius)
            # The new shell is a fixed physical clear-air layer, independent
            # of the legacy artistic atmosphere-height control.
            shell=by_role.get('ATMOSPHERE')
            if shell:
                shell.hide_render=not root['atmosphere']
                shell.hide_viewport=shell.hide_render
        if root.get('biome_enabled'):
            altitude=max(0.,cp.length-local_radius)
            # Centimetre shadow texels are useful on the ground, but exhaust
            # EEVEE's page pool during an orbital/atmospheric approach.
            root['op_shadow_resolution']=max(r*root['biome_grass_height']*.08,r*altitude*2./max(focal,1.))
        if inside_sky and root.get('lod_fit_clip',True):
            # A planet-sized far clip erases centimetre/metre-scale EEVEE
            # shadows. Keep a conservative local horizon range; the sky is a
            # World background and therefore needs no distant mesh shell.
            altitude=max(0.,cp.length-local_radius)
            horizon=math.sqrt(max(0.,2.*altitude+altitude*altitude))
            cam.data.clip_end=r*max(root.get('biome_view_distance',.001),horizon*1.25)
        if root.get('biome_enabled') and root.get('lod_fit_clip',True):
            # Keep the projection matrix representable in single precision.
            # An extreme far/near ratio collapses EEVEE's reconstructed sky ray
            # to a constant even when nearby object geometry still looks valid.
            cam.data.clip_start=max(.000001,r*.000000001,cam.data.clip_end*.000001)
        from . import terrain_regions
        height_guide=terrain_regions.height_sampler(root,local_radius) if root.get('biome_realism') else None
        verts,faces,stats=lod_mesh.build(tuple(cp),radius=local_radius,budget=remaining,height_guide=height_guide,**common)
        if root.get('biome_enabled'):split_living_surface(root,by_role['SURFACE'],verts,faces,cp,origin)
        else:
            by_role['SURFACE'].location=origin
            assign_mesh(by_role['SURFACE'],[tuple(v[j]-float(origin[j]) for j in range(3)) for v in verts] if origin.length else verts,faces)
            if 'FAR_SURFACE' in by_role:by_role['FAR_SURFACE'].hide_render=True;by_role['FAR_SURFACE'].hide_viewport=True
        if cloud_budget:
            cloud_radius=sample_radius(scene,root,clouds,cp)
            cv,cf,cs=lod_mesh.build(tuple(cp),radius=cloud_radius,budget=cloud_budget,**common)
            assign_mesh(clouds,cv,cf);fixed+=len(cf)
        total=len(faces)+fixed
        root['op_lod_triangles']=total;root['op_lod_depth']=stats['deepest']
        root['op_lod_budget_limited']=stats['budget_limited'];root['op_lod_ms']=(time.perf_counter()-t)*1000
        root['op_lod_status']=('Budget limited Â· ' if stats['budget_limited'] else '')+'%s triangles Â· depth %s'%(format(total,','),stats['deepest'])
        if root.get('biome_enabled') or any(o.get('op_role')=='BIOME_INSTANCES' for o in root.children):
            from . import biome
            biome.update(scene,root,ecam)
        root['op_total_triangles']=total+root.get('op_biome_triangles',0)
        if root.get('look_enabled'):
            from . import lookdev
            lookdev.validate_capture(scene,root)
        _cache[key]=signature(scene,root,cam.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    finally:_busy=False

def update_scene(scene,force=False):
    if _busy:return
    with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):
        for root in list(scene.objects):
            if root.get('op_root') and root.get('lod_enabled'):
                try:update(scene,root,force)
                except Exception as exc:root['op_lod_status']='LOD error: '+str(exc);print('OPEN_PLANET_LOD_ERROR',exc)

def restore_uniform(root):
    from .generator import sphere
    root['lod_enabled']=False
    quality=int(root.get('op_quality',256))
    for ob in root.children:
        role=ob.get('op_role')
        if role not in {'SURFACE','CLOUDS'}:continue
        seg=quality if role=='SURFACE' else max(128,quality//2)
        temp=sphere('OP temporary uniform mesh',root.users_collection[0],seg,seg//2);old=ob.data
        for m in old.materials:temp.data.materials.append(m)
        ob.data=temp.data;bpy.data.objects.remove(temp,do_unlink=True)
        if old.users==0:bpy.data.meshes.remove(old)
        ob.hide_render=False;ob.hide_viewport=False
    root['op_lod_status']='Uniform meshes restored';root.update_tag();_cache.clear()

def _timer():
    scenes=list(_pending);_pending.clear()
    if bpy.app.is_job_running('RENDER'):return None
    for name in scenes:
        scene=bpy.data.scenes.get(name)
        if scene and scene==bpy.context.scene:
            if name in _loaded:
                _loaded.discard(name)
                from .nodes import refresh_loaded_controls
                for root in scene.objects:
                    if root.get('op_root'):refresh_loaded_controls(root)
                bpy.context.view_layer.update()
            update_scene(scene)
    return None

@persistent
def _depsgraph(scene,dg):
    if _busy:return
    if any(r.get('op_root') and r.get('lod_enabled') and r.get('lod_auto',True) for r in scene.objects):
        _pending.add(scene.name)
        if not bpy.app.timers.is_registered(_timer):bpy.app.timers.register(_timer,first_interval=.15)

@persistent
def _frame(scene,*args):
    # A floating-origin move invalidates transforms as well as topology. Defer
    # that mutation until Blender finishes the frame dependency-graph callback.
    if any(o.get('biome_enabled') for o in scene.objects if o.get('op_root')):
        _pending.add(scene.name)
        if not bpy.app.timers.is_registered(_timer):bpy.app.timers.register(_timer,first_interval=.04)
    else:update_scene(scene)

@persistent
def _render(scene,*args):
    update_scene(scene,True)
    # A locked detail camera can differ from the moving render camera. Sky
    # altitude must still follow the latter when geometry is held for a shot.
    from . import lookdev
    for root in scene.objects:
        if root.get('op_root') and root.get('look_enabled'):
            lookdev.environment(scene,root)
            lookdev.lighting(scene,root)
            lookdev.validate_capture(scene,root)

@persistent
def _load(*args):
    _cache.clear();_pending.clear();_loaded.clear()
    for scene in bpy.data.scenes:
        if any(o.get('lod_enabled') for o in scene.objects):_pending.add(scene.name);_loaded.add(scene.name)
    if _pending and not bpy.app.timers.is_registered(_timer):bpy.app.timers.register(_timer,first_interval=.5)

def register():
    for collection,handler in ((bpy.app.handlers.depsgraph_update_post,_depsgraph),(bpy.app.handlers.frame_change_post,_frame),
                               (bpy.app.handlers.render_pre,_render),(bpy.app.handlers.load_post,_load)):
        if handler not in collection:collection.append(handler)

def unregister():
    for collection,handler in ((bpy.app.handlers.depsgraph_update_post,_depsgraph),(bpy.app.handlers.frame_change_post,_frame),
                               (bpy.app.handlers.render_pre,_render),(bpy.app.handlers.load_post,_load)):
        if handler in collection:collection.remove(handler)
    if bpy.app.timers.is_registered(_timer):bpy.app.timers.unregister(_timer)
    _cache.clear();_pending.clear();_loaded.clear()
