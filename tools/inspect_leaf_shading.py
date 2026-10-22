"""Inspect source material transport, without modifying the review file."""
import json
from pathlib import Path
import bpy
OUT=Path(__file__).resolve().parents[1]/'output/next-realism'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'daylight_grassland.blend'))
root=next(o for o in bpy.context.scene.objects if o.get('op_root'))
result={}
for ob in root.children:
    if ob.get('op_role')!='BIOME_SOURCE':continue
    for mat in ob.data.materials:
        if not mat or mat.name in result:continue
        data={'kinds':[ob.get('op_asset_kind')],'principled':[],'nodes':[]}
        for node in mat.node_tree.nodes:
            data['nodes'].append([node.name,node.bl_idname])
            if node.type!='BSDF_PRINCIPLED':continue
            values={}
            for name in ('Base Color','Roughness','Metallic','Subsurface Weight','Transmission Weight','Alpha','Normal'):
                socket=node.inputs[name]
                if socket.is_linked:values[name]=[socket.links[0].from_node.name,socket.links[0].from_socket.name]
                else:
                    val=socket.default_value;values[name]=list(val) if hasattr(val,'__len__') else val
            data['principled'].append(values)
        result[mat.name]=data
(OUT/'leaf_shading.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
