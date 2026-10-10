#!/usr/bin/env python3
"""Hash executable and shared-library artifacts, not just server launchers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('experiment', type=Path)
args = parser.parse_args()
records, digests = [], {}
builds = list(args.experiment.glob('build-*'))
builds += [Path('/srv/amd-halo/stack/.runtime/build-' + name) for name in ('vulkan', 'hip')]
for build in builds:
    if not (build / 'bin').is_dir():
        continue
    files = []
    for path in sorted((build / 'bin').iterdir()):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved not in digests:
            with resolved.open('rb') as handle:
                digests[resolved] = hashlib.file_digest(handle, 'sha256').hexdigest()
        files.append({'file': path.name, 'sha256': digests[resolved], 'bytes': path.stat().st_size,
                      'symlink_target': str(path.readlink()) if path.is_symlink() else None})
    cache = build / 'CMakeCache.txt'
    records.append({'build': str(build), 'files': files,
                    'cmake_cache': cache.read_text() if cache.exists() else None})
output = {'artifacts': records, 'uname': subprocess.check_output(['uname', '-a'], text=True).strip(),
          'rpm_packages': sorted(subprocess.check_output(['rpm', '-qa'], text=True).splitlines())}
(args.experiment / 'build-manifest.json').write_text(json.dumps(output, indent=2))
print('Recorded', len(records), 'builds and', len(digests), 'unique binary/library hashes')
