# SPDX-License-Identifier: GPL-3.0-or-later
"""Export real evaluated review geometry, shared assets and stable placements.

Run in Blender 5.2. Source .blend files are opened read-only and never saved.
Meshes use small local vertex coordinates; geographic offsets stay float64.
"""
import argparse,array,hashlib,json,math,shutil,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector,Euler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,biome,foliage,lookdev
from open_planet_lab.nodes import refresh_loaded_controls
parser=argparse.ArgumentParser();parser.add_argument('--sites',default='Forest,Grassland,Alpine,Desert,Ocean')
parser.add_argument('--inspect',action='store_true');parser.add_argument('--skip-prototypes',action='store_true')
parser.add_argument('--prototypes-only',action='store_true')
parser.add_argument('--metadata-only',action='store_true')
parser.add_argument('--source',type=Path,default=ROOT/'output/foliage-parity/Open-Planet-Designer-1.4.0-dev.2-Review.blend')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
DEST=ROOT/'godot/assets/generated';DEST.mkdir(parents=True,exist_ok=True)
SOURCE=args.source.resolve()
if not SOURCE.exists():raise RuntimeError('The packed Blender development review is required')
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene;lod.unregister()
r=next(o for o in s.objects if o.get('op_root'));refresh_loaded_controls(r)
s.frame_set(240);r['lod_enabled']=False;r['lod_auto']=False
lookdev.ensure(s,r);bpy.context.view_layer.update()
manifest={'schema':1,'source':str(SOURCE.relative_to(ROOT)) if SOURCE.is_relative_to(ROOT) else SOURCE.name,'source_sha256':hashlib.file_digest(SOURCE.open('rb'),'sha256').hexdigest(),
    'engine':'Godot 4.7.2','physical_units':'metres','sites':{},'prototypes':{},'licenses':'CC0 / USGS public domain; see THIRD_PARTY_NOTICES.md',
    'scope':'Frozen evaluated Blender coverage. Camera movement does not generate new terrain or plants.'}
if (args.prototypes_only or args.metadata_only) and (DEST/'manifest.json').exists():
    manifest['sites']=json.loads((DEST/'manifest.json').read_text())['sites']
if args.metadata_only:
    manifest=json.loads((DEST/'manifest.json').read_text())
    for site,record in manifest['sites'].items():
        cam=bpy.data.objects['Entry Camera · '+site]
        record['camera_fov_deg']=math.degrees(2.*math.atan(max(abs(v.y/v.z) for v in cam.data.view_frame(scene=s))))
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('GODOT_METADATA_UPDATED',flush=True);raise SystemExit(0)
if args.inspect:
    print('GODOT_INSPECT',json.dumps({'root':r.name,'radius':r['radius'],'metres_per_unit':s.unit_settings.scale_length,
        'cameras':[o.name for o in s.objects if o.type=='CAMERA'],'sources':[(o.name,o.get('op_asset_kind'),o.get('op_asset_lod')) for o in r.children if o.get('op_role')=='BIOME_SOURCE']}),flush=True)
    source=next(o for o in r.children if o.get('op_role')=='SURFACE');ev=source.evaluated_get(bpy.context.evaluated_depsgraph_get())
    print('GODOT_ATTRIBUTES',[(a.name,a.data_type,a.domain,len(a.data)) for a in ev.data.attributes],flush=True)
    raise SystemExit(0)

def texture_copy():
    folder=DEST/'scans';folder.mkdir(exist_ok=True)
    for name in ('leafy_grass','forrest_ground_01','brown_mud_leaves_01','rock_boulder_dry'):
        for channel in ('color','roughness','height'):
            ext='.jpg' if channel=='color' else '.png';path=ROOT/'open_planet_lab/assets/ground'/(name+'_'+channel+ext)
            image=bpy.data.images.load(str(path),check_existing=False)
            image.colorspace_settings.name='sRGB' if channel=='color' else 'Non-Color'
            image.scale(2048,2048);image.filepath_raw=str(folder/path.name);image.file_format='JPEG' if channel=='color' else 'PNG'
            image.save();bpy.data.images.remove(image)


def strip_air(mat):
    mat=mat.copy();tree=mat.node_tree
    for node in list(tree.nodes):
        if node.type!='GROUP' or not node.node_tree or not node.node_tree.get('op_air_owner'):continue
        surface=node.inputs['Surface'].links[0].from_socket
        if surface.node.type=='BSDF_PRINCIPLED':
            alpha=node.inputs['Alpha'];socket=surface.node.inputs['Alpha']
            if alpha.is_linked:tree.links.new(alpha.links[0].from_socket,socket)
            else:socket.default_value=alpha.default_value
        for link in list(node.outputs['Surface'].links):tree.links.new(surface,link.to_socket)
        tree.nodes.remove(node)
    fix=tree.nodes.get(foliage.FIX)
    if fix:
        image=fix.inputs[0].links[0].from_node.image;copy=image.copy()
        data=foliage.pixels(copy);data[:,:,2]=1.-data[:,:,2];copy.pixels.foreach_set(data.ravel());copy.pack()
        tex=fix.inputs[0].links[0].from_node;tex.image=copy
        for link in list(fix.outputs['Vector'].links):tree.links.new(tex.outputs['Color'],link.to_socket)
        tree.nodes.remove(fix)
    return mat


def prototypes():
    folder=DEST/'models';folder.mkdir(exist_ok=True)
    for ob in r.children:
        if ob.get('op_role')!='BIOME_SOURCE':continue
        kind=ob['op_asset_kind'];level=int(ob['op_asset_lod']);key=kind+'_'+str(level)
        path=folder/(key.lower()+'.glb')
        if not args.skip_prototypes or not path.exists():
            mesh=ob.data.copy();mesh.validate(verbose=False,clean_customdata=False)
            indices=np.empty(len(mesh.polygons),dtype=np.int32);mesh.polygons.foreach_get('material_index',indices)
            mesh.materials.clear()
            for mat in ob.data.materials:mesh.materials.append(strip_air(mat))
            mesh.polygons.foreach_set('material_index',indices)
            copy=bpy.data.objects.new(key,mesh);s.collection.objects.link(copy)
            for selected in bpy.context.selected_objects:selected.select_set(False)
            copy.select_set(True);bpy.context.view_layer.objects.active=copy
            bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,use_active_scene=True,
                export_apply=True,export_animations=False,export_cameras=False,export_lights=False,
                export_materials='EXPORT',export_yup=True)
            bpy.data.objects.remove(copy,do_unlink=True);bpy.data.meshes.remove(mesh)
        manifest['prototypes'][key]={'file':'models/'+path.name,'kind':kind,'level':level,'triangles':int(ob['op_triangles'])}
        print('GODOT_PROTOTYPE',key,path.stat().st_size,flush=True)


def attr(mesh,name,default):
    a=mesh.attributes.get('op_'+name)
    data=np.full(len(mesh.vertices),default,dtype=np.float32)
    if a and a.domain=='POINT' and a.data_type=='FLOAT':a.data.foreach_get('value',data)
    return data


def write_terrain(ob,folder,frame,anchor,metres):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        mesh.calc_loop_triangles();n=len(mesh.vertices)
        if not n:return []
        vertices=np.empty(n*3,dtype=np.float32);mesh.vertices.foreach_get('co',vertices)
        vertices=vertices.reshape(-1,3).astype(np.float64)
        matrix=np.array(ev.matrix_world,dtype=np.float64)
        vertices=((vertices@matrix[:3,:3].T+matrix[:3,3]-anchor)@frame.T)*metres
        normal=np.empty(n*3,dtype=np.float32);mesh.vertices.foreach_get('normal',normal)
        normal=normal.reshape(-1,3).astype(np.float64)@np.linalg.inv(matrix[:3,:3])@frame.T
        normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
        colors=np.column_stack([attr(mesh,'land',1.),attr(mesh,'forest',0.),attr(mesh,'mountain',0.),attr(mesh,'desert',0.)])
        faces=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('vertices',faces);faces=faces.reshape(-1,3)
        centres=vertices[faces].mean(axis=1);distance=np.linalg.norm(centres,axis=1)
        sizes=np.where(distance<1500,256.,np.where(distance<20000,4096.,np.where(distance<300000,65536.,1048576.)))
        coords=np.floor(centres/sizes[:,None]).astype(np.int64)
        keys=np.column_stack((sizes.astype(np.int64),coords));unique,inverse=np.unique(keys,axis=0,return_inverse=True)
        order=np.argsort(inverse,kind='stable');starts=np.searchsorted(inverse[order],np.arange(len(unique)+1))
        chunks=[]
        for index,key in enumerate(unique):
            subset=faces[order[starts[index]:starts[index+1]]]
            used,remap=np.unique(subset,return_inverse=True);points=vertices[used]
            centre=(points.min(axis=0)+points.max(axis=0))*.5
            local=(points-centre).astype('<f4');normals=normal[used].astype('<f4');col=colors[used].astype('<f4')
            # Stable site-space phase; scans fade out before distant UV precision matters.
            uv=(points[:,[0,2]]/2.).astype('<f4')
            path=folder/(ob.get('op_role','terrain').lower()+'_'+str(index)+'.opmesh')
            # Godot's front-face winding is clockwise; Blender's is CCW.
            indices=remap.reshape(-1,3)[:,[0,2,1]].astype('<i4').ravel()
            with path.open('wb') as file:
                file.write(np.asarray([len(used),len(indices)],dtype='<u4').tobytes())
                for data in (local,normals,col,uv,indices):file.write(data.tobytes())
            chunks.append({'file':path.relative_to(DEST).as_posix(),'center':centre.tolist(),'vertices':len(used),
                'triangles':len(indices)//3,'radius':float(np.linalg.norm(points-centre,axis=1).max())})
        return chunks
    finally:ev.to_mesh_clear()


def write_instances(folder,frame,anchor,metres):
    records=[];C=np.array(((1,0,0),(0,0,-1),(0,1,0)),dtype=float) # Godot local -> Blender local.
    counts={}
    for ob in r.children:
        if ob.get('op_role')!='BIOME_INSTANCES' or not len(ob.data.vertices):continue
        key=ob['op_scatter_key'];kind=key[:-1];level=int(key[-1]);mesh=ob.data;n=len(mesh.vertices)
        points=np.empty(n*3,dtype=np.float32);mesh.vertices.foreach_get('co',points);points=points.reshape(-1,3).astype(float)
        matrix=np.array(ob.matrix_world,dtype=float);positions=((points@matrix[:3,:3].T+matrix[:3,3]-anchor)@frame.T)*metres
        rotations=np.empty(n*3,dtype=np.float32);scales=np.empty(n*3,dtype=np.float32)
        mesh.attributes['op_rotation'].data.foreach_get('vector',rotations);mesh.attributes['op_scale'].data.foreach_get('vector',scales)
        ids=np.empty(n,dtype=np.int32);mesh.attributes['id'].data.foreach_get('value',ids)
        transforms=[];basis=frame@matrix[:3,:3]*metres
        for rot,scale in zip(rotations.reshape(-1,3),scales.reshape(-1,3)):
            transforms.append(basis@np.array(Euler(rot.tolist()).to_matrix())@np.diag(scale)@C)
        data=np.empty((n,12),dtype='<f4')
        # Rows are basis.x, basis.y, basis.z, origin (the MultiMesh format uses transposed rows below).
        data[:,:9]=np.array(transforms).transpose(0,2,1).reshape(n,9);data[:,9:]=positions
        path=folder/(kind.lower()+'_'+str(level)+'.opinstances')
        with path.open('wb') as file:
            file.write(np.asarray([n],dtype='<u4').tobytes());file.write(data.tobytes());file.write(ids.astype('<i4').tobytes())
        records.append({'file':path.relative_to(DEST).as_posix(),'prototype':kind+'_'+str(level),'kind':kind,'level':level,'count':n})
        counts[kind]=counts.get(kind,0)+n
    return records,counts


if not args.prototypes_only:texture_copy()
prototypes()
if args.prototypes_only:
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('GODOT_PROTOTYPES_REBUILT',flush=True);raise SystemExit(0)
for site in args.sites.split(','):
    start=time.perf_counter();cam=bpy.data.objects.get('Entry Camera · '+site)
    if not cam:raise RuntimeError('Missing review camera '+site)
    s.camera=cam;r.op_lod.camera=cam;s.frame_set(240);r['lod_enabled']=True
    lod.update(s,r,True);r['lod_enabled']=False;bpy.context.view_layer.update()
    cp,_=lod.logical_camera(r,cam.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    up=(r.matrix_world.to_quaternion()@cp.normalized()).normalized();east=Vector((0,0,1)).cross(up).normalized();north=up.cross(east)
    frame=np.array([east,up,-north],dtype=np.float64);anchor=np.array(cam.matrix_world.translation,dtype=np.float64)
    metres=s.unit_settings.scale_length;folder=DEST/site.lower();folder.mkdir(exist_ok=True)
    chunks=[]
    for ob in r.children:
        if ob.get('op_role') in {'SURFACE','FAR_SURFACE'} and not ob.hide_render:chunks+=write_terrain(ob,folder,frame,anchor,metres)
    instances,counts=write_instances(folder,frame,anchor,metres)
    # Camera basis converted from Blender's local camera axes to Godot's (-Z forward, +Y up).
    camera_basis=frame@np.array(cam.matrix_world.to_3x3(),dtype=float)
    centre=(np.array(r.matrix_world.translation,dtype=float)-anchor)@frame.T*metres
    sun=next(o for o in r.children if o.get('op_biome_light')=='Sun')
    sun_basis=frame@np.array(sun.matrix_world.to_3x3(),dtype=float)
    manifest['sites'][site]={'terrain':chunks,'instances':instances,'counts':counts,'camera_basis':camera_basis.T.reshape(-1).tolist(),
        'planet_center':centre.tolist(),'planet_radius':float(r['radius']*metres),
        'sun_basis':sun_basis.T.reshape(-1).tolist(),'sun_energy_blender':float(sun.data.energy),
        'source_terrain_triangles':int(r.get('op_lod_triangles',0)),'source_scatter_triangles':int(r.get('op_biome_triangles',0)),
        'elapsed_seconds':time.perf_counter()-start,'ground_moisture':float(r['look_moisture']),
        'exposure_ev':float(s.view_settings.exposure)}
    manifest['sites'][site]['camera_fov_deg']=math.degrees(2.*math.atan(max(abs(v.y/v.z) for v in cam.data.view_frame(scene=s))))
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('GODOT_SITE_EXPORTED',site,len(chunks),sum(counts.values()),time.perf_counter()-start,flush=True)
print('GODOT_EXPORT_COMPLETE',flush=True)
