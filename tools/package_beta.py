"""Package an explicit source version without including unrelated workspace files."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT
OUT = REPO / 'dist'
OUT.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version',default='1.4.0-dev.1')
parser.add_argument('--stage',choices=('development','beta'),default='development')
args=parser.parse_args()
tree=ast.parse((REPO/'open_planet_lab/__init__.py').read_text(encoding='utf-8'))
info=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
numeric='.'.join(str(x) for x in info['version'])
if args.version.split('-')[0]!=numeric:raise SystemExit('Requested package version does not match source bl_info')
if any(c not in '0123456789abcdefghijklmnopqrstuvwxyz.-' for c in args.version):raise SystemExit('Invalid version name')
target = OUT / ('Open-Planet-Designer-'+args.version+'.zip')
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
    for folder in ('daylight-ground','foliage'):
        for source in sorted((REPO / 'docs/media'/folder).glob('*.jpg')):
            archive.write(source,'open_planet_lab/docs/media/'+folder+'/'+source.name)
    info = {'name': 'Open Planet Designer', 'version': args.version, 'internal_module': 'open_planet_lab',
            'tested_blender': '5.2.0 LTS', 'stage': args.stage, 'ai_assisted': True}
    archive.writestr('open_planet_lab/RELEASE.json', json.dumps(info, indent=2))
with ZipFile(target) as archive:
    assert archive.testzip() is None
    source = archive.read('open_planet_lab/__init__.py').decode()
    assert "'name':'Open Planet Designer'" in source
    assert 'open_planet_lab/docs/EXPANDED_DISCUSSION.md' in archive.namelist()
digest = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
print(json.dumps({'file': str(target), 'bytes': target.stat().st_size, 'sha256': digest}))
