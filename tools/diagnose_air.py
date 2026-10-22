"""Ablation: preserve original leaf alpha while bypassing aerial perspective."""
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod
OUT=ROOT/'output/next-realism'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'daylight_grassland.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
lod.unregister()
tree=bpy.data.node_groups[r['op_air_group']]
socket=tree.nodes['View transmittance and in-scattering'].inputs[0]
for link in list(socket.links):tree.links.remove(link)
socket.default_value=0.
s.cycles.device='GPU'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
for engine,name in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
    s.render.engine=engine;s.render.filepath=str(OUT/('no_air_grassland_'+name+'.png'))
    bpy.ops.render.render(write_still=True)
