"""Create a clean, self-contained public beta example from the tested review."""
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import lod

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'output/planets/realism/Open_Planet_Realism_Priorities.blend'))
lod.unregister()
s = bpy.context.scene
s.render.resolution_x = 1280
s.render.resolution_y = 720
s.render.resolution_percentage = 100
s.render.fps = 24
s.render.fps_base = 1
s.render.filepath = '//beta-render.png'
s.render.engine = 'BLENDER_EEVEE'
s['op_note'] = 'Open Planet Designer 1.3.0-beta.1 | AI-assisted experimental beta'
for text in bpy.data.texts:
    if text.name.startswith('START HERE'):
        text.clear()
        text.write('OPEN PLANET DESIGNER 1.3.0-beta.1\n\n'
            'Experimental AI-assisted Blender add-on. Code: GPL-3.0-or-later.\n'
            'Source assets: Poly Haven CC0; USGS elevation: public domain.\n'
            'Repository: https://github.com/katfacey/Open-Planet-Designer\n\n'
            'N > Open Planet: choose Shot camera (Forest / Grassland / Alpine / Desert / Ocean).\n'
            'The file opens in Solid mode for responsiveness. F12 renders the actual materials.\n'
            'Install the complete beta ZIP to enable the sidebar and camera-adaptive updates.\n'
            'Refresh Camera Detail resolves the current shot; high detail may take time.\n\n'
            'Measured regions and detailed vegetation are bounded. Dense forest lighting still\n'
            'differs between Eevee and Cycles. Photorealism and seamless detail changes remain goals.\n'
            'See README, AI_DISCLOSURE and docs/REALISM_GUIDE in the repository.\n')
        text.filepath = ''
for image in bpy.data.images:
    if image.source == 'FILE' and image.packed_file:
        image.filepath = '//assets/' + Path(image.filepath).name
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'SOLID'
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
dest = ROOT / 'dist/Open-Planet-Designer-Beta-Demo.blend'
dest.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(dest), compress=True)
print('PUBLIC_BETA_SCENE_SAVED', dest, flush=True)
