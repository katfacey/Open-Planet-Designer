# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared distant-crown normals and temporary alpha-aware capture geometry.

Only bundled three-card tree proxies are supported. Detailed source foliage,
runtime geometry costs, alpha coverage and scatter placements are preserved.
"""
from contextlib import contextmanager
import json
import bpy
import numpy as np
from mathutils import Vector
from .foliage_math import support_loops, simplify_loop

KINDS = {'TREE','TREE_B','TREE_C','SAPLING','SAPLING_B','FIR','DEAD'}
FIX = 'OP · Crown camera-depth correction'
VERSION = 1


def sources(root):
    return [ob for ob in root.children if ob.get('op_role')=='BIOME_SOURCE'
            and ob.get('op_asset_lod')==2 and ob.get('op_asset_kind') in KINDS]


def atlas(material, channel):
    if not material or not material.use_nodes:return None
    return next((n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE'
                 and n.image and '_'+channel in n.image.filepath),None)


def pixels(image):
    w,h=image.size
    if not w or not h:raise ValueError('Missing crown atlas: '+image.name)
    data=np.empty(w*h*4,dtype=np.float32)
    image.pixels.foreach_get(data)
    return data.reshape(h,w,4)


def patch_sources(root):
    """Repair only legacy inward camera-Z maps; corrected atlases are untouched."""
    if not root.get('look_foliage_enabled'):return
    repaired=correct=skipped=empty=0;seen=set();diagnostics=[]
    for ob in sources(root):
        for mat in ob.data.materials:
            if not mat or mat.as_pointer() in seen:continue
            seen.add(mat.as_pointer())
            tree=mat.node_tree
            if not tree or 'source silhouette' not in mat.name:
                skipped+=1;continue
            if tree.nodes.get(FIX):repaired+=1;continue
            if mat.get('op_atlas_normal_convention')=='TANGENT_OUTWARD_Z_V1':
                correct+=1;continue
            color=atlas(mat,'color');normal=atlas(mat,'normal')
            if not color or not normal or tuple(color.size)!=tuple(normal.size):
                skipped+=1;continue
            alpha=pixels(color)[:,:,3]>.5
            z=pixels(normal)[:,:,2][alpha]
            if not len(z):
                if not np.any(pixels(color)[:,:,3]>.05):empty+=1
                else:skipped+=1
                continue
            inward=bool(np.median(z)<.5)
            diagnostics.append({'material':mat.name,'opaque_median_encoded_z':float(np.median(z)),
                                'legacy_inward_z':inward})
            if not inward:correct+=1;continue
            maps=[n for n in tree.nodes if n.type=='NORMAL_MAP' and n.inputs['Color'].is_linked
                  and n.inputs['Color'].links[0].from_node.type=='TEX_IMAGE'
                  and n.inputs['Color'].links[0].from_node.image==normal]
            if len(maps)!=1:skipped+=1;continue
            nm=maps[0];source=nm.inputs['Color'].links[0].from_socket
            fix=tree.nodes.new('ShaderNodeVectorMath');fix.name=FIX;fix.label='Outward crown normal · shared engines'
            fix.operation='MULTIPLY_ADD';fix.inputs[1].default_value=(1,1,-1)
            fix.inputs[2].default_value=(0,0,1);fix['op_foliage_fix_version']=VERSION
            tree.links.new(source,fix.inputs[0]);tree.links.new(fix.outputs['Vector'],nm.inputs['Color'])
            repaired+=1
    root['op_foliage_status']=f'{repaired} repaired; {correct} correct; {empty} empty views; {skipped} unsupported'
    if diagnostics:root['op_foliage_diagnostics']=json.dumps(diagnostics)


def restore(root):
    for ob in sources(root):
        for mat in ob.data.materials:
            if not mat or not mat.use_nodes:continue
            tree=mat.node_tree;fix=tree.nodes.get(FIX)
            if not fix or fix.get('op_foliage_fix_version')!=VERSION:continue
            if fix.inputs[0].is_linked:
                original=fix.inputs[0].links[0].from_socket
                for link in list(fix.outputs['Vector'].links):tree.links.new(original,link.to_socket)
            tree.nodes.remove(fix)
    root['look_foliage_enabled']=False;root['op_foliage_status']='Legacy crown lighting restored'


def capture_mesh(ob, resolution=64):
    """Conservative alpha support, tessellated with holes; original UVs retained.

    This mesh is used only during the static light capture. A max filter keeps
    occupied leaf cells and thin branches. Transparent cells create no surfels.
    """
    original=ob.data;vertices=[];faces=[];materials=[];uvs=[]
    expected=actual=0.
    if len(original.polygons)!=3 or any(len(p.vertices)!=4 for p in original.polygons):
        raise ValueError('Capture support requires the bundled three-quad crown: '+ob.name)
    for polygon in original.polygons:
        color=atlas(original.materials[polygon.material_index],'color')
        if not color:raise ValueError('No color/alpha crown atlas: '+ob.name)
        alpha=pixels(color)[:,:,3];h,w=alpha.shape
        if w%resolution or h%resolution:raise ValueError('Crown atlas size must divide capture support grid')
        support=alpha.reshape(resolution,h//resolution,resolution,w//resolution).max(axis=(1,3))>.05
        loops=[simplify_loop(loop) for loop in support_loops(support)]
        if not loops:continue
        curve=bpy.data.curves.new('OP temporary alpha contours','CURVE')
        curve.dimensions='2D';curve.fill_mode='FRONT';curve.resolution_u=1
        temp=mesh=None
        try:
            for loop in loops:
                spline=curve.splines.new('POLY');spline.points.add(len(loop)-1);spline.use_cyclic_u=True
                for point,(x,y) in zip(spline.points,loop):point.co=(x/resolution,y/resolution,0,1)
            temp=bpy.data.objects.new('OP temporary alpha tessellation',curve)
            bpy.context.scene.collection.objects.link(temp);bpy.context.view_layer.update()
            mesh=bpy.data.meshes.new_from_object(temp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            mesh.calc_loop_triangles()
            expected+=float(support.sum())/resolution**2
            actual+=sum(face.area for face in mesh.polygons)
            # Use the source UV transform, rather than assuming corner ordering.
            layer=original.uv_layers.active
            source_uv=[layer.data[i].uv.copy() for i in polygon.loop_indices]
            if any((uv-reference).length>1e-6 for uv,reference in zip(source_uv,
                    [Vector(x) for x in ((0,0),(1,0),(1,1),(0,1))])):
                raise ValueError('Unsupported edited crown UVs: '+ob.name)
            corners=[original.vertices[i].co.copy() for i in polygon.vertices];offset=len(vertices)
            for vertex in mesh.vertices:
                u,v=vertex.co.x,vertex.co.y
                vertices.append(tuple(corners[0]+(corners[1]-corners[0])*u+(corners[3]-corners[0])*v));uvs.append((u,v))
            for triangle in mesh.loop_triangles:
                indices=list(triangle.vertices)
                if triangle.normal.z<0:indices.reverse()
                faces.append(tuple(offset+i for i in indices));materials.append(polygon.material_index)
        finally:
            if mesh:bpy.data.meshes.remove(mesh)
            if temp:bpy.data.objects.remove(temp,do_unlink=True)
            bpy.data.curves.remove(curve)
    if abs(actual-expected)>1e-5:raise ValueError('Alpha contour tessellation changed support area')
    mesh=bpy.data.meshes.new(ob.name+' · temporary capture support')
    try:
        mesh.from_pydata(vertices,[],faces);mesh.update()
        for mat in original.materials:mesh.materials.append(mat)
        layer=mesh.uv_layers.new(name='UVMap')
        for face,material in zip(mesh.polygons,materials):
            face.material_index=material
            for li in face.loop_indices:layer.data[li].uv=uvs[mesh.loops[li].vertex_index]
        mesh['op_capture_support_area']=actual;mesh['op_capture_grid']=resolution
        return mesh
    except Exception:
        bpy.data.meshes.remove(mesh);raise


@contextmanager
def capture_sources(root):
    """Restore six-triangle render sources even when building/baking fails."""
    swapped=[];derived=[];stats=[]
    try:
        if root.get('look_foliage_enabled'):
            for ob in sources(root):
                original=ob.data;mesh=capture_mesh(ob);derived.append(mesh)
                swapped.append((ob,original));ob.data=mesh;ob.update_tag(refresh={'DATA'})
                stats.append({'kind':ob.get('op_asset_kind'),'support_triangles':len(mesh.polygons),
                              'support_area_uv':mesh['op_capture_support_area']})
        bpy.context.view_layer.update()
        yield stats
    finally:
        for ob,original in swapped:ob.data=original;ob.update_tag(refresh={'DATA'})
        bpy.context.view_layer.update()
        for mesh in derived:
            if mesh.users==0:bpy.data.meshes.remove(mesh)


def enable(scene,root):
    from . import lookdev,biome
    if not root.get('look_enabled'):raise RuntimeError('Upgrade Daylight & Ground first')
    if not root.get('biome_realism'):raise RuntimeError('Upgrade Terrain & Forest Structure first')
    lookdev.ensure(scene,root)
    root['look_foliage_enabled']=True
    biome.assets(root);patch_sources(root)
    probe=lookdev.probe_for(root)
    if probe:probe.hide_render=True;probe.hide_viewport=True
    root['op_gi_status']='Foliage repaired — bake current shot again'
