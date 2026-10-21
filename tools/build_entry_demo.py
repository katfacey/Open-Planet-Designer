import sys,json,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab
open_planet_lab.register()
from open_planet_lab import generator,lod
out=ROOT/'output'/'planets'/'entry';out.mkdir(exist_ok=True)
s,r=generator.create_entry_demo()
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX' and '5090' in d.name
report={}
frames=tuple(int(x) for x in sys.argv[sys.argv.index('--')+1].split(',')) if '--' in sys.argv else (1,100,145,190,240)
for frame in frames:
    s.frame_set(frame);bpy.context.view_layer.update();lod.update(s,r,True)
    s.render.resolution_x=960;s.render.resolution_y=540
    stats={k:r.get(k) for k in ('op_lod_triangles','op_lod_depth','op_lod_ms','op_lod_status')}
    surface=next(o for o in r.children if o.get('op_role')=='SURFACE')
    cp=r.matrix_world.inverted()@s.camera.matrix_world.translation
    stats['camera_altitude_radius']=cp.length-lod.sample_radius(s,r,surface,cp)
    for engine,name in [('BLENDER_EEVEE','eevee'),('CYCLES','cycles')]:
        s.render.engine=engine;s.cycles.device='GPU';s.cycles.samples=128
        s.render.filepath=str(out/f'entry_{frame:03}_{name}.png');t=time.perf_counter();bpy.ops.render.render(write_still=True);stats[name+'_seconds']=time.perf_counter()-t
    report[str(frame)]=stats;print('ENTRY_FRAME',frame,stats,flush=True)
s.frame_set(1);s.render.engine='BLENDER_EEVEE';s.render.resolution_x=1280;s.render.resolution_y=720
s.render.filepath=str(out/'entry_render.png')
guide=bpy.data.texts.new('START HERE · Atmospheric Entry')
guide.write('OPEN PLANET DESIGNER 1.1\n\nScrub frames 1-240: orbit, atmosphere, cloud altitude, low terrain.\nN sidebar > Open Planet > Camera Detail & Entry.\nThe selected scene camera controls the adaptive mesh.\nNear/far distances are fractions of planet radius.\nBudget limited means the cap is respected but target detail is unmet.\n\nThis is bounded procedural detail, not literal infinite resolution.\nAtmosphere is analytical; clouds remain displaced translucent shells.\nFull guide: PLANET_ENTRY_GUIDE.md in the project folder.\n')
(out/'entry_verification.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Open_Planet_Atmospheric_Entry.blend'),compress=True)
print('ENTRY_DEMO_COMPLETE',flush=True)
