# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch original CC0 OpenGL normal maps; retain provenance and checksums."""
import concurrent.futures
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'godot/assets/appearance'
DEST.mkdir(parents=True, exist_ok=True)
NAMES = ('forrest_ground_01', 'leafy_grass', 'brown_mud_leaves_01', 'rock_boulder_dry')


def prepare(name):
    request = urllib.request.Request('https://api.polyhaven.com/files/' + name,
                                     headers={'User-Agent': 'OpenPlanetDesigner asset preparation'})
    cached = DEST / (name + '-files.json')
    if cached.exists():
        metadata = json.loads(cached.read_text())
    else:
        with urllib.request.urlopen(request, timeout=60) as response:
            metadata = json.load(response)
        cached.write_text(json.dumps(metadata))
    source = metadata['nor_gl']['2k']['png']
    target = DEST / (name + '_normal.png')
    if not target.exists() or target.stat().st_size != source['size']:
        with urllib.request.urlopen(source['url'], timeout=120) as response:
            data = response.read()
        assert len(data) == source['size'], name
        if source.get('md5'):
            assert hashlib.md5(data).hexdigest() == source['md5'], name
        target.write_bytes(data)
    return {'asset': name, 'source': 'https://polyhaven.com/a/' + name,
            'license': 'CC0-1.0', 'license_url': 'https://polyhaven.com/license',
            'file': target.name, 'channel': 'OpenGL normal, original 2k PNG',
            'download': source['url'], 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(prepare, NAMES))

for name, width in [('forrest_ground_03', 2.0), ('forest_leaves_02', 3.0)]:
    cached = DEST / (name + '-files.json')
    if cached.exists():
        metadata = json.loads(cached.read_text())
    else:
        request = urllib.request.Request('https://api.polyhaven.com/files/' + name,
                                         headers={'User-Agent': 'OpenPlanetDesigner asset preparation'})
        with urllib.request.urlopen(request, timeout=60) as response:
            metadata = json.load(response)
        cached.write_text(json.dumps(metadata))
    for key, channel, extension in [('diff', 'color', 'jpg'), ('nor_gl', 'normal', 'png'),
                                     ('rough', 'roughness', 'jpg'), ('disp', 'height', 'png'),
                                     ('ao', 'ao', 'jpg')]:
        aliases = {'diff': 'Diffuse', 'rough': 'Rough', 'disp': 'Displacement', 'ao': 'AO'}
        source = metadata[key if key in metadata else aliases.get(key, key)]['2k'][extension]
        target = DEST / (name + '_' + channel + '.' + extension)
        if not target.exists() or target.stat().st_size != source['size']:
            with urllib.request.urlopen(source['url'], timeout=120) as response:
                data = response.read()
            assert len(data) == source['size']
            if source.get('md5'): assert hashlib.md5(data).hexdigest() == source['md5']
            target.write_bytes(data)
        records.append({'asset': name, 'source': 'https://polyhaven.com/a/' + name,
                        'license': 'CC0-1.0', 'license_url': 'https://polyhaven.com/license',
                        'width_m': width, 'channel': channel, 'file': target.name,
                        'download': source['url'], 'bytes': target.stat().st_size,
                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
sky = DEST / 'earth_daylight.hdr'
shutil.copyfile(ROOT / 'open_planet_lab/assets/ground/sky.hdr', sky)
records.append({'asset': 'kloofendal_48d_partly_cloudy_puresky',
                'source': 'https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky',
                'license': 'CC0-1.0', 'license_url': 'https://polyhaven.com/license',
                'file': sky.name, 'channel': 'HDR daylight environment, retained original 2k asset',
                'sha256': hashlib.sha256(sky.read_bytes()).hexdigest()})
(DEST / 'CREDITS.json').write_text(json.dumps({'schema': 1, 'assets': records}, indent=2) + '\n')
configured = 0
for folder in (DEST, ROOT / 'godot/assets/catalog/scans'):
    for path in folder.glob('*.import'):
        text = path.read_text()
        text = text.replace('mipmaps/generate=false', 'mipmaps/generate=true')
        text = text.replace('compress/mode=0', 'compress/mode=2')
        if path.name.endswith('_normal.png.import'):
            text = text.replace('compress/normal_map=0', 'compress/normal_map=1')
        path.write_text(text)
        configured += 1
print(json.dumps({'asset_files': len(records), 'downloaded_asset_bytes': sum(r.get('bytes', 0) for r in records)}))
print('Configured 3D imports:', configured, '(run again after the first Godot import if zero)')
