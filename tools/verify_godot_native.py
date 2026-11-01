# SPDX-License-Identifier: GPL-3.0-or-later
"""Independently verify OPDF frame data and publish compact native-alpha evidence.

Requires NumPy and Pillow. Run after the named check_godot_runtime.ps1 routes have finished.
Raw machine-local reports stay under output/; the public summary has no local paths.
"""
import hashlib
import json
import math
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
CASES = ('native-final-forest', 'native-final-seam', 'native-final-orbit',
         'native-final-cold', 'native-final-warm')
NAMESPACES = dict(zip(CASES, ('guarded-final-1', 'guarded-final-2', 'guarded-final-3',
                              'guarded-matched-720-1', 'guarded-matched-720-1')))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_case(tag):
    report = read(OUT / f'{tag}.json')
    process = read(OUT / f'{tag}-process.json')
    assert process['cache_namespace'] == report['metadata']['cache_namespace'] == NAMESPACES[tag], tag
    raw = (OUT / f'{tag}.json.frames').read_bytes()
    assert raw[:4] == b'OPDF', tag
    length, = struct.unpack_from('<I', raw, 4)
    header = json.loads(raw[8:8 + length])
    count = header['frames']
    assert count == report['flight_frame_count'] and count > 0, tag
    values = np.frombuffer(raw, dtype='<f4', offset=8 + length)
    assert values.size == count * len(header['columns']), tag
    values = values.reshape(len(header['columns']), count)
    assert np.isfinite(values).all() and (values >= 0).all(), tag
    for key, column in zip(header['columns'], values):
        sorted_values = np.sort(column)
        for percentile, index in (('p50', count // 2), ('p95', math.ceil(count * .95) - 1),
                                  ('p99', math.ceil(count * .99) - 1)):
            actual = float(sorted_values[index])
            assert abs(actual - report['flight_distributions'][key][percentile]) < .0001, (tag, key, percentile)
    intervals = values[header['columns'].index('frame_ms')]
    stalls = [{'flight_frame_index': int(i), 'frame_ms': float(intervals[i])}
              for i in np.flatnonzero(intervals > 100)]
    assert process['exit_code'] == 0 and not process['engine_errors'], tag
    logs = ''.join((OUT / f'{tag}{suffix}').read_text(encoding='utf-8-sig')
                   for suffix in ('.log', '-errors.log'))
    assert not re.search(r'SCRIPT ERROR|ERROR:', logs), tag
    assert process['standalone'] and process['managed_module_check_completed'], tag
    assert not process['managed_runtime_modules_detected'], tag
    assert report['dropped_frames'] == 0, tag
    with Image.open(OUT / f'{tag}.png') as image:
        assert list(image.size) == report['resolution'], (tag, image.size, report['resolution'])
    peaks = report['peaks']
    limits = {'resident_tiles': 2048, 'active_tiles': 384, 'desired_leaves': 384,
              'pending_workers': 2, 'ecology_pending': 2, 'vegetation_instances': 30000,
              'expanded_scatter_triangles': 5000000}
    for key, limit in limits.items():
        assert peaks[key] <= limit, (tag, key, peaks[key], limit)
    flight = [sample for sample in report['samples'] if sample['phase'] == 'flight']
    assert flight[-1]['route_s'] >= process['seconds'] - .5, tag
    thirds = []
    for index in range(3):
        samples = [s for s in flight if index / 3 <= s['route_s'] / process['seconds'] < (index + 1) / 3]
        thirds.append({key: max(s[key] for s in samples) for key in
                       ('resident_tiles', 'vegetation_instances', 'render_buffer_bytes', 'render_texture_bytes')})
    return {'tag': tag, 'route': process['route'], 'flight_seconds': process['seconds'],
            'warmup_seconds': process['warmup_seconds'], 'framebuffer': report['resolution'],
            'cache_namespace': process['cache_namespace'], 'flight_frames': count,
            'dropped_frames': 0, 'frame_columns_independently_verified': True,
            'frame_distributions_ms': report['flight_distributions'],
            'flight_max_frame_ms': float(intervals.max()), 'flight_stalls_over_100ms': stalls,
            'including_warmup_max_frame_ms': peaks['frame_ms'],
            'process_peak_working_set_bytes': process['observed_peak_working_set_bytes'],
            'exit_code': 0, 'engine_errors': False, 'managed_runtime_modules_detected': False,
            'peaks': {k: peaks[k] for k in (*limits, 'render_texture_bytes', 'render_buffer_bytes',
                                          'rebases', 'cache_hits', 'ecology_cache_hits', 'evictions',
                                          'unmet_error_pixels')},
            'thirds_peak_counters': thirds, 'report_sha256': sha(OUT / f'{tag}.json'),
            'raw_frames_sha256': sha(OUT / f'{tag}.json.frames')}


def main():
    tested = read(OUT / 'native-tested-source.json')
    for name, digest in tested['runtime_files'].items():
        assert sha(ROOT / 'godot' / name) == digest, name
    cases = [verify_case(tag) for tag in CASES]
    assert cases[-2]['framebuffer'] == cases[-1]['framebuffer'] == [1280, 720]
    assert cases[-2]['flight_seconds'] == cases[-1]['flight_seconds'] == 300
    core = read(OUT / 'native-core-checks.json')
    lifecycle = read(OUT / 'native-streaming-lifecycle.json')
    assert core['passed'] and all(core['checks'].values()) and len(core['checks']) == 27
    assert lifecycle['passed'] and all(lifecycle['checks'].values())
    pck = ROOT / 'dist/godot-runtime/OpenPlanetDesigner.pck'
    isolated = OUT / 'standalone-native-final-check/OpenPlanetDesigner.pck'
    assert sha(pck) == sha(isolated)
    result = {
        'schema': 1, 'date': '2026-11-01', 'version': '0.2.0-alpha.1',
        'engine': core['engine'], 'renderer': 'Forward+ / Vulkan',
        'machine': {**read(OUT / 'native-machine.json'), 'gpu': 'NVIDIA GeForce RTX 5090'},
        'runtime_source_sha256': tested.get('runtime_source_sha256', tested.get('source_sha256')),
        'pck_sha256': sha(pck), 'core_checks': core['checks'],
        'delayed_worker_lifecycle_checks': lifecycle['checks'], 'standalone_routes': cases,
        'risk_probe_rgb_difference_percent': read(OUT / 'native-risk-measurements.json'),
        'decisions': {
            'precision': 'Scalar float64 canonical arithmetic; origin subtraction before float32 vectors.',
            'indirect_light': 'SDFGI disabled by default; rebase probe has localized leaf-edge differences.',
            'air': 'Diagnostic spherical depth pass only; not enabled in the production runtime.',
        },
        'scope': [
            'Same Windows development machine, other desktop applications present; not a clean-machine qualification.',
            'Two matched 300-second 1280x720 woodland runs share route speed and cache namespace; cold means fresh application cache, not driver shader cache.',
            'Forest, seam and orbit routes render 1920x1080. Every reported window size is checked against the PNG readback dimensions; the pinned engine ViewportTexture size query can include an extra desktop scale factor.',
            'Peaks include warmup; timing distributions contain all recorded flight frames. Runtime timings are subsystem measurements, not additive CPU totals.',
            'Engine memory counters are estimates, not total driver VRAM. RSS is a separately observed process peak. Bounded route counters do not prove arbitrary-duration leak freedom.',
            'Hard tile/job/instance/triangle limits passed. Disk targets and main-thread upload timings are soft interval targets.',
            'No 8GB GPU, 16GB system RAM, Linux or separate clean Windows machine qualification.',
            'Photographic appearance, seamless temporal foliage, production atmosphere/clouds and animated water remain open.',
        ],
    }
    # The earlier fingerprint fixture uses an aggregate key; preserve it explicitly.
    if result['runtime_source_sha256'] is None:
        result['runtime_source_sha256'] = hashlib.sha256(json.dumps(tested['runtime_files'], sort_keys=True).encode()).hexdigest()
    target = ROOT / 'docs/verification/godot-native.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'verified_routes': len(cases), 'core_checks': len(core['checks']),
                      'lifecycle_checks': len(lifecycle['checks']), 'report': target.name}, indent=2))


if __name__ == '__main__':
    main()
