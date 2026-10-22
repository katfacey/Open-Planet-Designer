"""Test larger finite lighting coverage without changing scene materials."""
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod,lookdev
OUT=ROOT/'output/next-realism'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'daylight_grassland.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
lod.unregister();r['lod_enabled']=False
r['look_probe_extent']=500.;r['look_probe_capture']=150.;r['look_probe_resolution']=32
lookdev.bake(s,r)
s.render.engine='BLENDER_EEVEE';s.render.filepath=str(OUT/'wide_probe_grassland_eevee.png')
bpy.ops.render.render(write_still=True)
print('WIDE_CAPTURE_COMPLETE',flush=True)
