# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the Windows alpha and an editable, hydrated native Godot project."""
import hashlib,json,subprocess
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'godot';DIST=ROOT/'dist';APP=DIST/'godot-runtime'
VERSION='0.2.0-alpha.1'
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
runtime_files={}
for path in sorted(PROJECT.rglob('*')):
    rel=path.relative_to(PROJECT)
    if not path.is_file() or rel.parts[0] in ('.godot','assets','tests','scenes'):continue
    if path.suffix in ('.gd','.gdshader','.tscn','.tres','.godot') and path.name not in ('viewer.gd','import_data.gd','main.tscn'):
        runtime_files[rel.as_posix()]=sha(path)
source_tree=hashlib.sha256(json.dumps(runtime_files,sort_keys=True).encode()).hexdigest()
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
for name in ('OpenPlanetDesigner.exe','OpenPlanetDesigner.pck','GODOT_NOTICES.txt'):
    if not (APP/name).exists():raise RuntimeError('Export the native app first: '+name)
for name in ('LICENSE','AI_DISCLOSURE.md','THIRD_PARTY_NOTICES.md'):(APP/name).write_bytes((ROOT/name).read_bytes())
build={'version':VERSION,'stage':'native-streaming-alpha','engine':'Godot 4.7.2','source_revision':revision,'source_dirty':dirty,
    'runtime_source_sha256':source_tree,'runtime_files':runtime_files,'pck_sha256':sha(APP/'OpenPlanetDesigner.pck'),
    'ai_assisted':True,'consumer_hardware_qualified':False,'source_url':'https://github.com/katfacey/Open-Planet-Designer/tree/godot-import'}
(APP/'BUILD.json').write_text(json.dumps(build,indent=2)+'\n')
archives=[]
def finish(path):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        names=archive.namelist();assert len(names)==len(set(names))
    archives.append({'file':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'crc_ok':True,'entries':len(names)})
windows=DIST/f'Open-Planet-Designer-Godot-{VERSION}-Windows.zip'
with ZipFile(windows,'w',ZIP_DEFLATED,compresslevel=1) as archive:
    for path in sorted(APP.rglob('*')):
        if path.is_file():archive.write(path,'Open-Planet-Designer/'+path.relative_to(APP).as_posix())
finish(windows)
source=DIST/f'Open-Planet-Designer-Godot-{VERSION}-Source.zip'
with ZipFile(source,'w',ZIP_DEFLATED,compresslevel=1) as archive:
    for path in sorted(PROJECT.rglob('*')):
        rel=path.relative_to(PROJECT)
        if not path.is_file() or any(p.startswith('.') for p in rel.parts):continue
        if rel.parts[:2]==('assets','generated') or rel.parts[0]=='scenes':continue
        if path.name in ('main.tscn','viewer.gd','viewer.gd.uid','import_data.gd','import_data.gd.uid','check_materials.gd','check_materials.gd.uid'):continue
        archive.write(path,'Open-Planet-Designer-Source/godot/'+rel.as_posix())
    for directory in ('docs','tools','tests','open_planet_lab'):
        for path in sorted((ROOT/directory).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:continue
            if path.name=='godot-native-package.json':continue  # Published alongside archives; avoid a self-referential checksum.
            if directory=='open_planet_lab' and path.suffix not in ('.py','.json','.md'):continue
            if directory=='tools' and path.suffix not in ('.py','.ps1'):continue
            archive.write(path,'Open-Planet-Designer-Source/'+path.relative_to(ROOT).as_posix())
    for name in ('README.md','LICENSE','AI_DISCLOSURE.md','THIRD_PARTY_NOTICES.md'):
        archive.write(ROOT/name,'Open-Planet-Designer-Source/'+name)
    archive.writestr('Open-Planet-Designer-Source/BUILD.json',json.dumps(build,indent=2))
    archive.write(APP/'GODOT_NOTICES.txt','Open-Planet-Designer-Source/GODOT_NOTICES.txt')
finish(source)
report={'version':VERSION,'build':build,'archives':archives,'source_includes_native_assets':True,'source_includes_frozen_import':False,'godot_cache_included':False}
(ROOT/'output/native-package.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'archives':archives,'source_revision':revision,'source_dirty':dirty,'runtime_source_sha256':source_tree},indent=2))
