"""Extract the distributable, import it independently and render its shaders."""
import json,sys,time
from pathlib import Path
from zipfile import ZipFile
import bpy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/next-realism'
destination=OUT/'package-smoke-1.4.0-dev.1'
archive_path=ROOT/'dist/Open-Planet-Designer-1.4.0-dev.1.zip'
with ZipFile(archive_path) as archive:
    assert archive.testzip() is None,'Archive CRC failure'
    info=json.loads(archive.read('open_planet_lab/RELEASE.json'))
    assert info['version']=='1.4.0-dev.1' and info['stage']=='development'
    assert 'open_planet_lab/docs/media/daylight-ground/forest-comparison.jpg' in archive.namelist()
    for name in archive.namelist():
        assert (destination/name).resolve().is_relative_to(destination.resolve()),'Unsafe archive path'
    archive.extractall(destination)
sys.path.insert(0,str(destination))
import open_planet_lab
assert Path(open_planet_lab.__file__).resolve().is_relative_to(destination.resolve())
assert open_planet_lab.bl_info['version']==(1,4,0)
open_planet_lab.register()
from open_planet_lab import lod,lookdev
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Open-Planet-Designer-1.4-Development-Review.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'))
s.frame_set(s.frame_current);lod.unregister()
r['lod_enabled']=False;r['lod_auto']=False
lookdev.ensure(s,r);lookdev.rebuild_materials(r);lookdev.wrap_assets(r)
start=time.perf_counter();lookdev.bake(s,r)
bake_seconds=time.perf_counter()-start
s.render.engine='BLENDER_EEVEE';s.render.filepath=str(OUT/'package_smoke_forest.png')
start=time.perf_counter();bpy.ops.render.render(write_still=True)
render_seconds=time.perf_counter()-start
assert lookdev.validate_capture(s,r),'Capture changed after rendering'
unpacked=[image.name for image in bpy.data.images if image.users and image.source=='FILE' and not image.packed_file]
assert not unpacked,unpacked
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Open-Planet-Designer-1.4-Development-Review.blend'),compress=True)
report={'version':info['version'],'stage':info['stage'],'archive_crc_ok':True,'independent_package_import':True,
    'register_ok':True,'new_ground_shader_render_ok':True,'capture_valid_after_render':True,'all_used_file_images_packed':True,
    'bake_seconds':bake_seconds,'render_seconds':render_seconds}
(OUT/'package_smoke.json').write_text(json.dumps(report,indent=2))
print('PACKAGE_SMOKE_COMPLETE',json.dumps(report),flush=True)
