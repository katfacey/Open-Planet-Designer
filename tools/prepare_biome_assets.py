"""Create compact, packed model LODs; retain source UVs and actual branches."""
import bpy,json,math,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'open_planet_lab/assets';OUT.mkdir(exist_ok=True)
collection=bpy.data.collections.new('OP Biome Source Models')
bpy.context.scene.collection.children.link(collection)
report={};export=[]

def source(asset,name):
    with bpy.data.libraries.load(str(ROOT/'research/cc0'/asset/(asset+'_1k.blend')),link=False) as (src,dst):dst.objects=[name]
    ob=dst.objects[0];collection.objects.link(ob)
    for mat in ob.data.materials:
        if not mat:continue
        images=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        diffuse=next((im for im in images if '_diff_' in im.filepath),None)
        if 'trunk_a' in mat.name:diffuse=next((im for im in images if 'trunk_a_diff' in im.filepath),diffuse)
        alpha=next((im for im in images if '_alpha_' in im.filepath),None)
        rough=next((im for im in images if '_rough_' in im.filepath),None)
        normal=next((im for im in images if '_nor_gl_' in im.filepath),None)
        for im in (diffuse,alpha,rough,normal):
            if im:
                im.filepath=str(ROOT/'research/cc0'/asset/'textures'/Path(im.filepath).name)
                im.reload();im.pack()
        mat.node_tree.nodes.clear();nodes=mat.node_tree.nodes;links=mat.node_tree.links
        out=nodes.new('ShaderNodeOutputMaterial');bsdf=nodes.new('ShaderNodeBsdfPrincipled')
        links.new(bsdf.outputs['BSDF'],out.inputs['Surface'])
        if diffuse:
            n=nodes.new('ShaderNodeTexImage');n.image=diffuse;links.new(n.outputs['Color'],bsdf.inputs['Base Color'])
        if alpha:
            n=nodes.new('ShaderNodeTexImage');n.image=alpha;n.image.colorspace_settings.name='Non-Color'
            clip=nodes.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.42
            links.new(n.outputs['Color'],clip.inputs[0]);links.new(clip.outputs[0],bsdf.inputs['Alpha'])
        if rough:
            n=nodes.new('ShaderNodeTexImage');n.image=rough;n.image.colorspace_settings.name='Non-Color';links.new(n.outputs['Color'],bsdf.inputs['Roughness'])
        if normal:
            n=nodes.new('ShaderNodeTexImage');n.image=normal;n.image.colorspace_settings.name='Non-Color'
            nm=nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.6
            links.new(n.outputs['Color'],nm.inputs['Color']);links.new(nm.outputs[0],bsdf.inputs['Normal'])
        mat.surface_render_method='DITHERED'
    return ob

def lods(ob,kind,targets):
    raw=ob.data.copy();raw.calc_loop_triangles();raw_tri=len(raw.loop_triangles)
    coords=[v.co.copy() for v in raw.vertices]
    lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)))
    hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
    scale=(hi.z-lo.z) if kind!='ROCK' else max(hi.x-lo.x,hi.y-lo.y)
    center=Vector(((lo.x+hi.x)*.5,(lo.y+hi.y)*.5,lo.z))
    for v in raw.vertices:v.co=(v.co-center)/scale
    tree_base=None
    for level,target in enumerate(targets):
        mesh=raw.copy();obj=bpy.data.objects.new(f'OP_{kind}_LOD{level}',mesh);collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        if kind.startswith('TREE') and level:
            import bmesh
            obj.data=tree_base.copy();bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table()
            visited=set();drop=[];rng=random.Random(300+level);fraction=.30 if level==1 else .035
            # Disconnected needle cards set a lower bound on ordinary decimation.
            # Thin complete twig islands, then enlarge retained islands for distant coverage.
            for vert in bm.verts:
                if vert in visited or not vert.link_faces or any(f.material_index!=2 for f in vert.link_faces):continue
                stack=[vert];component=[];visited.add(vert)
                while stack:
                    item=stack.pop();component.append(item)
                    for edge in item.link_edges:
                        other=edge.other_vert(item)
                        if other not in visited:visited.add(other);stack.append(other)
                if rng.random()>fraction:drop.extend(component)
                else:
                    center=sum((v.co for v in component),Vector())/len(component)
                    for v in component:v.co=center+(v.co-center)*min(3.5,1/math.sqrt(fraction))
            if level==2:
                dropped=set(drop)
                drop.extend(v for v in bm.verts if v not in dropped and v.link_faces and all(f.material_index in (0,3) for f in v.link_faces))
            bmesh.ops.delete(bm,geom=list(set(drop)),context='VERTS');bm.to_mesh(obj.data);bm.free()
        obj.data.calc_loop_triangles();before=len(obj.data.loop_triangles)
        if before>target:
            mod=obj.modifiers.new('Prepared source LOD','DECIMATE');mod.ratio=target/before;mod.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if kind.startswith('TREE') and level==0:tree_base=obj.data.copy()
        obj.data.calc_loop_triangles();obj['op_triangles']=len(obj.data.loop_triangles)
        obj['op_asset_kind']=kind;obj['op_asset_lod']=level;obj['op_source']='Poly Haven CC0'
        report[obj.name]={'source_triangles':raw_tri,'prepared_triangles':obj['op_triangles']}
        export.append(obj);obj.select_set(False)
    bpy.data.objects.remove(ob,do_unlink=True)

tree=source('pine_tree_01','pine_tree_01_a_LOD2');lods(tree,'TREE',(416451,24000,1200))
tree=source('pine_tree_01','pine_tree_01_b_LOD2');lods(tree,'TREE_B',(450000,24000,1200))
tree=source('pine_tree_01','pine_tree_01_c_LOD2');lods(tree,'TREE_C',(450000,24000,1200))
grass=source('grass_medium_01','grass_medium_01_mid_a_LOD2');lods(grass,'WILDGRASS',(659,240,64))
rock=source('boulder_01','boulder_01_LOD0');lods(rock,'ROCK',(124000,3000,180))
fern=source('fern_02','fern_02_a');lods(fern,'FERN',(12000,700,100))
bpy.data.libraries.write(str(OUT/'biome_library.blend'),set(export),fake_user=True,compress=True)
(OUT/'LOD_MANIFEST.json').write_text(json.dumps(report,indent=2))
(OUT/'CREDITS.json').write_text((ROOT/'research/cc0/CREDITS.json').read_text())
print('BIOME_ASSETS_PREPARED',json.dumps(report),flush=True)
