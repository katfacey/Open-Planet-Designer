"""Restore runtime assets from the complete release ZIP into a source checkout."""
import argparse
import hashlib
import shutil
from pathlib import Path
from zipfile import ZipFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('archive', type=Path)
parser.add_argument('--sha256', help='Expected SHA256 from the release SHA256SUMS.txt')
args = parser.parse_args()
if args.sha256:
    actual = hashlib.file_digest(args.archive.open('rb'), 'sha256').hexdigest()
    if actual.lower() != args.sha256.lower():
        raise SystemExit('Archive checksum does not match')
root = Path(__file__).resolve().parents[1]
with ZipFile(args.archive) as archive:
    required = {'open_planet_lab/assets/realism_library.blend', 'open_planet_lab/assets/biome_library.blend'}
    if not required.issubset(archive.namelist()):
        raise SystemExit('Use the full installable release archive, not the source ZIP')
    corrupt = archive.testzip()
    if corrupt:
        raise SystemExit('Archive CRC check failed: ' + corrupt)
    count = 0
    for item in archive.infolist():
        if item.is_dir() or not item.filename.startswith('open_planet_lab/assets/'):
            continue
        target = (root / item.filename).resolve()
        if not target.is_relative_to(root / 'open_planet_lab/assets'):
            raise SystemExit('Unsafe archive member')
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(item) as source, target.open('wb') as destination:
            shutil.copyfileobj(source, destination)
        count += 1
print('Restored', count, 'runtime asset files')
