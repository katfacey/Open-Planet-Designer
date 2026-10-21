"""Run in a factory-startup background Blender. Does not touch the city file."""
import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import generator
scene,root=generator.create_demo()
out=ROOT/'output'/'planets';out.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Open_Planet_Lab.blend'))
scene.render.resolution_x=640;scene.render.resolution_y=640
scene.render.filepath=str(out/'terra_eevee_v2.png')
bpy.ops.render.render(write_still=True)
scene.render.engine='CYCLES';scene.cycles.device='GPU'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX' and '5090' in device.name
scene.render.filepath=str(out/'terra_cycles_v2.png')
bpy.ops.render.render(write_still=True)
print('OPEN_PLANET_INITIAL_COMPLETE',flush=True)
