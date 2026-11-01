# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the native Godot import project and generated assets, excluding caches."""
import hashlib,json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'godot';OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
manifest=json.loads((PROJECT/'assets/generated/manifest.json').read_text())
for name in manifest['sites']:
    if not (PROJECT/'assets/generated'/(name.lower()+'_review.scn')).exists():raise RuntimeError('Generate native review scenes first')
target=OUT/'Open-Planet-Designer-Godot-Import-0.1.zip'
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=1) as archive:
    for path in sorted(PROJECT.rglob('*')):
        relative=path.relative_to(PROJECT)
        if not path.is_file() or '.godot' in relative.parts:continue
        archive.write(path,'Open-Planet-Designer-Godot/'+relative.as_posix())
    for name in ('LICENSE','AI_DISCLOSURE.md','THIRD_PARTY_NOTICES.md'):
        archive.write(ROOT/name,'Open-Planet-Designer-Godot/'+name)
    for path in sorted((ROOT/'open_planet_lab/assets').rglob('*.json')):
        archive.write(path,'Open-Planet-Designer-Godot/source-credits/'+path.relative_to(ROOT/'open_planet_lab/assets').as_posix())
    archive.writestr('Open-Planet-Designer-Godot/BUILD.json',json.dumps({'stage':'migration-prototype','version':'0.1',
        'engine':'Godot 4.7.2','source_blender_sha256':manifest['source_sha256'],'frozen_coverage':True,'ai_assisted':True},indent=2))
with ZipFile(target) as archive:
    assert archive.testzip() is None
report={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),
    'archive_crc_ok':True,'contains_generated_assets':True,'godot_import_cache_included':False}
(ROOT/'output/godot-package.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
