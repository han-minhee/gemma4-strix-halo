#!/usr/bin/env python3
"""Verify both transferred BF16 shards before installing them without overwrite."""
import argparse
import hashlib
import json
import os
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--staging', type=Path, required=True)
p.add_argument('--models', type=Path, required=True)
p.add_argument('--record', type=Path, required=True)
a = p.parse_args()
versions = json.loads((Path(__file__).resolve().parents[1] / 'versions.json').read_text())
records = []
if a.record.exists():
    raise SystemExit('Installation record already exists')
for name in ('BF16_1', 'BF16_2'):
    entry = versions['files'][name]
    source = a.staging / Path(entry['path']).name
    target = a.models / source.name
    if target.exists():
        raise SystemExit('Refuse to replace a model: ' + str(target))
    with source.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if digest != entry['sha256'] or source.stat().st_size != entry['size']:
        raise SystemExit('Transferred BF16 integrity failure: ' + str(source))
    records.append({'name': name, 'source': str(source), 'file': str(target),
                    'sha256': digest, 'bytes': source.stat().st_size})
    print('Verified', name, digest, flush=True)
for row in records:
    # Both directories are on the same experiment volume. link() refuses overwrite.
    os.link(row['source'], row['file'])
    Path(row['source']).unlink()
record = {'model_repo': versions['model_repo'], 'model_revision': versions['model_revision'],
          'status': 'installed', 'files': records}
temp = a.record.with_suffix('.tmp')
temp.write_text(json.dumps(record, indent=2) + '\n')
temp.replace(a.record)
print('Installed both verified BF16 shards', flush=True)
