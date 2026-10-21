"""Package the renamed public beta without including unrelated workspace files."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT
OUT = REPO / 'dist'
OUT.mkdir(exist_ok=True)
target = OUT / 'Open-Planet-Designer-1.3.0-beta.1.zip'
with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
    for source in sorted((REPO / 'open_planet_lab').glob('*.py')):
        archive.write(source, 'open_planet_lab/' + source.name)
    for source in sorted((ROOT / 'open_planet_lab/assets').rglob('*')):
        if source.is_file() and source.suffix in {'.blend', '.png', '.jpg', '.hdr', '.json'}:
            archive.write(source, source.relative_to(ROOT).as_posix())
    for name in ('LICENSE', 'AI_DISCLOSURE.md', 'THIRD_PARTY_NOTICES.md'):
        archive.write(REPO / name, 'open_planet_lab/' + name)
    readme = (REPO / 'README.md').read_text(encoding='utf-8').split('## Beta demo')[0]
    readme += ('## Beta demo\n\n25 seconds, 1280 Ã— 720 at 24 fps: a brief intro followed by one continuous descent. '
               '[Watch the video on the project page](https://github.com/katfacey/Open-Planet-Designer#beta-demo).\n')
    archive.writestr('open_planet_lab/README.md', readme)
    for source in sorted((REPO / 'docs').glob('*.md')):
        archive.write(source, 'open_planet_lab/docs/' + source.name)
    for source in sorted((REPO / 'docs/verification').glob('*.json')):
        archive.write(source, 'open_planet_lab/docs/verification/' + source.name)
    info = {'name': 'Open Planet Designer', 'version': '1.3.0-beta.1', 'internal_module': 'open_planet_lab',
            'tested_blender': '5.2.0 LTS', 'stage': 'beta', 'ai_assisted': True}
    archive.writestr('open_planet_lab/BETA_RELEASE.json', json.dumps(info, indent=2))
with ZipFile(target) as archive:
    assert archive.testzip() is None
    source = archive.read('open_planet_lab/__init__.py').decode()
    assert "'name':'Open Planet Designer'" in source
    assert 'open_planet_lab/docs/EXPANDED_DISCUSSION.md' in archive.namelist()
digest = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
print(json.dumps({'file': str(target), 'bytes': target.stat().st_size, 'sha256': digest}))
