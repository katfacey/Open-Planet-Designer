"""Prepare age variants and silhouette/normal atlases from CC0 source meshes."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'open_planet_lab/assets'
ATLAS=OUT/'canopy';ATLAS.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
for ob in list(scene.objects):bpy.data.objects.remove(ob,do_unlink=True)
scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=16
scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0
cam=bpy.data.objects.new('Atlas camera',bpy.data.cameras.new('Atlas camera'));scene.collection.objects.link(cam)
cam.data.type='ORTHO';cam.data.ortho_scale=1.04;scene.camera=cam
collection=bpy.data.collections.new('OP Realism Source Models');scene.collection.children.link(collection)
report={};export=[];materials={}

def load(asset,name):
    with bpy.data.libraries.load(str(ROOT/'research/cc0'/asset/(asset+'_1k.blend')),link=False) as (src,dst):dst.objects=[name]
    ob=dst.objects[0];collection.objects.link(ob);ob.hide_render=False;ob.hide_set(False)
    for slot,mat in enumerate(list(ob.data.materials)):
        if not mat:
            mat=bpy.data.materials.new(asset+' unassigned source slot');mat.use_nodes=True;ob.data.materials[slot]=mat
        key=(asset,mat.name.split('.')[0])
        if key in materials:ob.data.materials[slot]=materials[key];continue
        for n in mat.node_tree.nodes:
            if n.type=='TEX_IMAGE' and n.image:
                n.image.filepath=str(ROOT/'research/cc0'/asset/'textures'/Path(n.image.filepath).name)
                if Path(n.image.filepath).exists():n.image.reload();n.image.pack()
        vector_attribute=None
        for node in mat.node_tree.nodes:
            if node.type!='TEX_IMAGE' or not node.inputs['Vector'].is_linked:continue
            upstream=node.inputs['Vector'].links[0].from_node
            while upstream.type=='REROUTE' and upstream.inputs[0].is_linked:upstream=upstream.inputs[0].links[0].from_node
            if upstream.type=='ATTRIBUTE':vector_attribute=upstream.attribute_name;break
        images=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and n.image.packed_file]
        own=[im for im in images if mat.name.split('.')[0]+'_' in Path(im.filepath).name]
        if own:images=own
        diffuse=next((i for i in images if '_diff_' in i.filepath),None)
        alpha=next((i for i in images if '_alpha_' in i.filepath),None)
        rough=next((i for i in images if '_rough_' in i.filepath),None)
        normal=next((i for i in images if '_nor_gl_' in i.filepath),None)
        mat.node_tree.nodes.clear();ns=mat.node_tree.nodes;ls=mat.node_tree.links
        bs=ns.new('ShaderNodeBsdfPrincipled');bs.name='Shared PBR surface';bs.inputs['Roughness'].default_value=.72
        out=ns.new('ShaderNodeOutputMaterial');ls.new(bs.outputs[0],out.inputs['Surface'])
        uv=None
        if vector_attribute:
            attr=ns.new('ShaderNodeAttribute');attr.attribute_name=vector_attribute;uv=attr.outputs['Vector']
        for im,socket in ((diffuse,'Base Color'),(rough,'Roughness'),(alpha,'Alpha')):
            if im:
                n=ns.new('ShaderNodeTexImage');n.image=im
                if uv:ls.new(uv,n.inputs['Vector'])
                if socket!='Base Color':im.colorspace_settings.name='Non-Color'
                if socket=='Alpha':
                    clip=ns.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.35
                    ls.new(n.outputs['Color'],clip.inputs[0]);ls.new(clip.outputs[0],bs.inputs[socket])
                else:ls.new(n.outputs['Color'],bs.inputs[socket])
        if normal:
            n=ns.new('ShaderNodeTexImage');n.image=normal;normal.colorspace_settings.name='Non-Color'
            if uv:ls.new(uv,n.inputs['Vector'])
            nm=ns.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.7;ls.new(n.outputs['Color'],nm.inputs['Color']);ls.new(nm.outputs[0],bs.inputs['Normal'])
        mat.surface_render_method='DITHERED'
        # Individual leaves, not a tree-sized slab, determine transmission thickness.
        if alpha:out.inputs['Thickness'].default_value=.00015
        materials[key]=mat
    return ob

def normalized(ob,kind):
    raw=ob.data.copy();coords=[v.co.copy() for v in raw.vertices]
    lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
    scale=max(hi.x-lo.x,hi.y-lo.y) if kind=='ROCK' else hi.z-lo.z
    center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    for v in raw.vertices:v.co=(v.co-center)/scale
    return raw,dict(source_height=float(hi.z-lo.z),source_width=float(max(hi.x-lo.x,hi.y-lo.y)),normalizing_scale=float(scale))

def render_atlas(ob,kind):
    originals=list(ob.data.materials);indices=[f.material_index for f in ob.data.polygons];bake=[]
    for mat in originals:
        m=mat.copy();ns=m.node_tree.nodes;ls=m.node_tree.links;bs=ns.get('Shared PBR surface');out=next(n for n in ns if n.type=='OUTPUT_MATERIAL')
        emission=ns.new('ShaderNodeEmission');emission.name='Atlas unlit albedo'
        if bs.inputs['Base Color'].is_linked:ls.new(bs.inputs['Base Color'].links[0].from_socket,emission.inputs['Color'])
        else:emission.inputs['Color'].default_value=bs.inputs['Base Color'].default_value
        geom=ns.new('ShaderNodeNewGeometry');tr=ns.new('ShaderNodeVectorTransform');tr.vector_type='NORMAL';tr.convert_from='WORLD';tr.convert_to='CAMERA';ls.new(geom.outputs['Normal'],tr.inputs[0])
        mul=ns.new('ShaderNodeVectorMath');mul.operation='MULTIPLY_ADD';mul.inputs[1].default_value=(.5,.5,.5);mul.inputs[2].default_value=(.5,.5,.5);ls.new(tr.outputs[0],mul.inputs[0])
        normal=ns.new('ShaderNodeEmission');normal.name='Atlas tangent normal';ls.new(mul.outputs[0],normal.inputs['Color'])
        transparent=ns.new('ShaderNodeBsdfTransparent');mix=ns.new('ShaderNodeMixShader');mix.name='Atlas alpha'
        if bs.inputs['Alpha'].is_linked:ls.new(bs.inputs['Alpha'].links[0].from_socket,mix.inputs[0])
        else:mix.inputs[0].default_value=1.
        ls.new(transparent.outputs[0],mix.inputs[1]);ls.new(emission.outputs[0],mix.inputs[2]);ls.new(mix.outputs[0],out.inputs['Surface']);bake.append(m)
    ob.data.materials.clear()
    for mat in bake:ob.data.materials.append(mat)
    for polygon,index in zip(ob.data.polygons,indices):polygon.material_index=index
    paths=[]
    for view,position,target,up in (('front',(0,-4,.5),(0,0,.5),'Y'),('side',(4,0,.5),(0,0,.5),'Y'),('top',(0,0,4),(0,0,0),'Y')):
        cam.location=position;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z',up).to_euler()
        pair={}
        for mode in ('color','normal'):
            scene.view_settings.view_transform='Standard' if mode=='color' else 'Raw'
            for mat in bake:
                ns=mat.node_tree.nodes;mat.node_tree.links.new(ns['Atlas unlit albedo' if mode=='color' else 'Atlas tangent normal'].outputs[0],ns['Atlas alpha'].inputs[2])
            path=ATLAS/(kind.lower()+'_'+view+'_'+mode+'.png');scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True);pair[mode]=path
        paths.append(pair)
    ob.data.materials.clear()
    for mat in originals:ob.data.materials.append(mat)
    for polygon,index in zip(ob.data.polygons,indices):polygon.material_index=index
    for mat in bake:bpy.data.materials.remove(mat)
    return paths

def proxy(kind,paths):
    verts=[(-.52,0,-.02),(.52,0,-.02),(.52,0,1.02),(-.52,0,1.02),
           (0,-.52,-.02),(0,.52,-.02),(0,.52,1.02),(0,-.52,1.02),
           (-.52,-.52,.72),(.52,-.52,.72),(.52,.52,.72),(-.52,.52,.72)]
    mesh=bpy.data.meshes.new('Crown silhouette '+kind);mesh.from_pydata(verts,[],[(0,1,2,3),(4,5,6,7),(8,9,10,11)]);mesh.update()
    uv=mesh.uv_layers.new()
    for polygon in mesh.polygons:
        for li,coord in zip(polygon.loop_indices,((0,0),(1,0),(1,1),(0,1))):uv.data[li].uv=coord
    for i,pair in enumerate(paths):
        mat=bpy.data.materials.new(kind+' · source silhouette '+str(i));mat.use_nodes=True;ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=ns.get('Principled BSDF');bs.inputs['Roughness'].default_value=.78
        color=ns.new('ShaderNodeTexImage');color.image=bpy.data.images.load(str(pair['color']),check_existing=True);color.image.pack()
        ls.new(color.outputs['Color'],bs.inputs['Base Color']);ls.new(color.outputs['Alpha'],bs.inputs['Alpha'])
        tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(pair['normal']),check_existing=True);tex.image.colorspace_settings.name='Non-Color';tex.image.pack()
        nm=ns.new('ShaderNodeNormalMap');ls.new(tex.outputs['Color'],nm.inputs['Color']);ls.new(nm.outputs[0],bs.inputs['Normal']);mat.surface_render_method='DITHERED'
        mesh.materials.append(mat);mesh.polygons[i].material_index=i
    return mesh

def prepare(asset,name,kind,mid_target):
    ob=load(asset,name);raw,dimensions=normalized(ob,kind);ob.data=raw;ob.location=(0,0,0);ob.rotation_euler=(0,0,0);ob.scale=(1,1,1)
    raw.calc_loop_triangles();original=len(raw.loop_triangles)
    far=proxy(kind,render_atlas(ob,kind)) if kind in ('TREE','TREE_B','TREE_C','SAPLING','SAPLING_B','FIR','DEAD') else None
    for level in range(3):
        mesh=far if level==2 and far else raw.copy();obj=bpy.data.objects.new(f'OP_{kind}_LOD{level}',mesh);collection.objects.link(obj)
        if level and not (level==2 and far):
            target=mid_target if level==1 else max(36,int(mid_target*.09));mesh.calc_loop_triangles()
            if len(mesh.loop_triangles)>target:
                bpy.context.view_layer.objects.active=obj;mod=obj.modifiers.new('Topology reduction; preserve source cards','DECIMATE');mod.ratio=target/len(mesh.loop_triangles);mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
        obj.data.calc_loop_triangles();obj['op_triangles']=len(obj.data.loop_triangles);obj['op_asset_kind']=kind;obj['op_asset_lod']=level;obj['op_source']='Poly Haven CC0';obj['op_library_version']=13
        report[obj.name]=dict(source_asset=asset,source_object=name,source_triangles=original,prepared_triangles=obj['op_triangles'],**dimensions)
        obj.hide_render=True;export.append(obj)
    bpy.data.objects.remove(ob,do_unlink=True)
    print('PREPARED_REALISM',kind,original,[report[o.name]['prepared_triangles'] for o in export[-3:]],dimensions,flush=True)

for suffix,kind in (('a','TREE'),('b','TREE_B'),('c','TREE_C')):prepare('pine_tree_01','pine_tree_01_'+suffix+'_LOD1',kind,60000)
prepare('pine_sapling_small','pine_sapling_small_a','SAPLING',18000)
prepare('pine_sapling_small','pine_sapling_small_c','SAPLING_B',18000)
prepare('fir_sapling_medium','fir_sapling_medium_a_LOD1','FIR',28000)
# Reuse scanned trunk/dead-branch geometry, without leaf cards, as a snag.
ob=load('pine_tree_01','pine_tree_01_a_LOD2')
import bmesh
bm=bmesh.new();bm.from_mesh(ob.data)
drop=[f for f in bm.faces if 'twig' in ob.data.materials[f.material_index].name]
bmesh.ops.delete(bm,geom=drop,context='FACES');bm.to_mesh(ob.data);bm.free()
# The temporary source is exported through the same normalizer/atlas path.
raw,dimensions=normalized(ob,'DEAD');ob.data=raw
paths=render_atlas(ob,'DEAD');far=proxy('DEAD',paths)
for level,target in enumerate((45000,8000,6)):
    obj=bpy.data.objects.new(f'OP_DEAD_LOD{level}',far if level==2 else raw.copy());collection.objects.link(obj)
    obj.data.calc_loop_triangles()
    if level<2 and len(obj.data.loop_triangles)>target:
        bpy.context.view_layer.objects.active=obj;mod=obj.modifiers.new('Snag reduction','DECIMATE');mod.ratio=target/len(obj.data.loop_triangles);bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.calc_loop_triangles();obj['op_triangles']=len(obj.data.loop_triangles);obj['op_asset_kind']='DEAD';obj['op_asset_lod']=level;obj['op_library_version']=13;obj['op_source']='Poly Haven CC0';obj.hide_render=True;export.append(obj)
    report[obj.name]=dict(source_asset='pine_tree_01',modifications='Removed needle cards for dead snag',prepared_triangles=obj['op_triangles'],**dimensions)
bpy.data.objects.remove(ob,do_unlink=True)
for suffix,kind in (('a','FERN'),('b','FERN_B'),('c','FERN_C')):prepare('fern_02','fern_02_'+suffix,kind,650)
prepare('grass_medium_01','grass_medium_01_mid_a_LOD0','WILDGRASS',360)
prepare('grass_medium_01','grass_medium_01_mid_c_LOD0','WILDGRASS_B',360)
prepare('boulder_01','boulder_01_LOD0','ROCK',3500)
bpy.data.libraries.write(str(OUT/'realism_library.blend'),set(export),fake_user=True,compress=True)
(OUT/'REALISM_LOD_MANIFEST.json').write_text(json.dumps(report,indent=2))
(OUT/'CREDITS.json').write_text((ROOT/'research/cc0/CREDITS.json').read_text())
print('REALISM_LIBRARY_COMPLETE',len(export),flush=True)
