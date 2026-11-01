# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect structural/render evidence and check the original CC0 asset bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


core = read(OUT / 'visual-core.json')
lifecycle = read(OUT / 'visual-lifecycle.json')
gpu = read(OUT / 'visual-gpu-checks.json')
for report in (core, lifecycle, gpu):
    assert report['passed'] and all(report['checks'].values())
assert core['count'] == 29
credits = read(ROOT / 'godot/assets/appearance/CREDITS.json')
for asset in credits['assets']:
    assert asset['license'] == 'CC0-1.0'
    assert sha(ROOT / 'godot/assets/appearance' / asset['file']) == asset['sha256']
study = read(ROOT / 'godot/assets/appearance/study.json')
assert study['instances'] == 59212 and study['terrain_triangles'] == 500000
standalone = read(OUT / 'woodland-export.json')
assert standalone['instances'] == study['instances'] and standalone['source_sha256'] == study['source_sha256']
native = read(OUT / 'woodland-native-export.json')
assert native['dropped_frames'] == 0 and native['peaks']['expanded_scatter_triangles'] <= 12000000
assert native['peaks']['resident_tiles'] <= 2048 and native['peaks']['vegetation_instances'] <= 30000
for tag in ('woodland-export', 'woodland-native-export', 'visual-gpu-checks'):
    logs = (OUT / (tag + '.log')).read_text(encoding='utf-8-sig') + (OUT / (tag + '-errors.log')).read_text(encoding='utf-8-sig')
    assert 'SCRIPT ERROR' not in logs and 'ERROR:' not in logs
proxies = read(ROOT / 'godot/assets/appearance/proxies.json')
for proxy in proxies['proxies'].values():
    path = ROOT / 'godot' / proxy['file'].removeprefix('res://')
    proxy['sha256'] = sha(path)
    assert proxy['triangles'] < proxy['source_triangles']
result = {
    'version': '0.2.0-alpha.2', 'date': '2026-11-01',
    'direction': 'Natural daylight with subtle cinematic color; Earth assets first.',
    'scope': 'Bounded original-layout study plus shared native look improvements; photographic approval open.',
    'engine': core['engine'], 'gpu': native['gpu'],
    'core_checks': core['checks'], 'lifecycle_checks': lifecycle['checks'], 'gpu_checks': gpu['checks'],
    'python_reference_tests': 23, 'study': study,
    'study_asset_sha256': sha(ROOT / 'godot/assets/appearance/forest_study.scn'),
    'cc0_original_files_verified': len(credits['assets']), 'asset_manifest_sha256': sha(ROOT / 'godot/assets/appearance/CREDITS.json'),
    'hybrid_representations': proxies['proxies'], 'exported_study': standalone,
    'native_export': {'resolution': native['resolution'], 'flight_frames': native['flight_frame_count'],
                      'flight_distributions_ms': native['flight_distributions'],
                      'peaks': {key: native['peaks'][key] for key in
                                ('resident_tiles', 'active_tiles', 'expanded_scatter_triangles', 'vegetation_instances')},
                      'dropped_frames': 0, 'engine_errors': False},
    'pck_sha256': sha(ROOT / 'dist/godot-visual/OpenPlanetDesigner.pck'),
    'limits': ['RTX 5090 development machine; no consumer-GPU or clean-machine qualification.',
               'Study detail/population are fixed; different native layout and FOV are not a controlled rendering comparison.',
               'Local SDFGI is not enabled/qualified in the rebased streamer.',
               'Canopy/card appearance, procedural grass, close debris and moving-view consistency remain open.',
               'No planetary atmosphere, clouds, animated water, full NPR preset or other-planet visual qualification.'],
}
target = ROOT / 'docs/verification/godot-woodland-look.json'
target.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'core': len(core['checks']), 'lifecycle': len(lifecycle['checks']), 'gpu': len(gpu['checks']),
                  'cc0_files': len(credits['assets']), 'proof': target.name}))
