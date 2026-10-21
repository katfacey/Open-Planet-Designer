"""Synchronize saved node graphs with the packaged source and add native notes."""
import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab;open_planet_lab.register()
from open_planet_lab import generator,lod,nodes
OUT=ROOT/'output/planets/realism';path=OUT/'Open_Planet_Realism_Priorities.blend'
bpy.ops.wm.open_mainfile(filepath=str(path));s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
s.camera=bpy.data.objects['Entry Camera · Forest'];s.oplab.entry_camera=s.camera;s.frame_set(240)
generator.upgrade_entry(s,r,refresh=False);lod.update(s,r,True);nodes.refresh_loaded_controls(r);bpy.context.view_layer.update()
text=bpy.data.texts.get('START HERE - Realism 1.3') or bpy.data.texts.new('START HERE - Realism 1.3');text.clear()
text.write('OPEN PLANET DESIGNER 1.3 - REALISM STRUCTURE PASS\n\n'
    'Priorities: forest ages/forms; measured regional terrain; coherent distance detail.\n'
    'Choose Shot camera in N > Open Planet. Five cameras share this world.\n'
    'Living Surface: Upgrade Terrain & Forest Structure; individual tree distance; separate detail budgets.\n'
    'Previous scene and package are preserved beside this review.\n\n'
    'All terrain and foreground plants use actual geometry. Distant tree detail uses source color/normal atlases.\n'
    'Review quality is for offline shots. Freeze Living Geometry for a fixed preview; refresh for a changed camera.\n'
    'Dense forest still needs a lighting/parity pass. See PLANET_REALISM_GUIDE.md for tests, sources and limits.\n')
s['op_note']='Open Planet Designer 1.3 | first three realism priorities | see PLANET_REALISM_GUIDE.md'
surface=next(o for o in r.children if o.get('op_role')=='SURFACE')
for ob in bpy.context.selected_objects:ob.select_set(False)
surface.select_set(True);bpy.context.view_layer.objects.active=surface
assert r['op_lod_triangles']<=r['lod_budget'] and r['op_biome_triangles']<=r['biome_budget']
assert any(n.name=='Physical USGS region canyon' for n in surface.modifiers[0].node_group.nodes)
bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
print('REALISM_FINALIZED',r['op_lod_status'],r['op_biome_status'],flush=True)
