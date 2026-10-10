#!/usr/bin/env python3
"""Build the experimental ROCmFP4 target directly from verified BF16 shards."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def checksum(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--models', type=Path, required=True)
p.add_argument('--output', type=Path, required=True, help='New output directory for shards, log and provenance')
a = p.parse_args()
versions = json.loads((Path(__file__).resolve().parents[1] / 'versions.json').read_text())
sources = []
for name in ('BF16_1', 'BF16_2'):
    entry = versions['files'][name]
    path = a.models / Path(entry['path']).name
    digest = checksum(path)
    if path.stat().st_size != entry['size'] or digest != entry['sha256']:
        raise SystemExit('BF16 integrity failure: ' + str(path))
    sources.append({'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
a.output.mkdir(parents=True, exist_ok=False)
prefix = a.output / 'gemma-4-31B-it-ROCmFP4-STRIX_LEAN'
command = [str(a.binary), '--keep-split', sources[0]['path'], str(prefix),
           'Q4_0_ROCMFP4_STRIX_LEAN', '8']
record = {'status': 'running', 'started': time.time(), 'source_revision': versions['model_revision'],
          'sources': sources, 'command': command, 'quantizer_sha256': checksum(a.binary)}
provenance = a.output / 'conversion.json'
provenance.write_text(json.dumps(record, indent=2) + '\n')
with (a.output / 'conversion.log').open('w') as log:
    completed = subprocess.run(command, stdout=log, stderr=log)
record['exit_code'] = completed.returncode
record['outputs'] = [{'path': str(path), 'sha256': checksum(path), 'bytes': path.stat().st_size}
                     for path in sorted(a.output.glob(prefix.name + '-*.gguf'))]
record['status'] = 'ok' if completed.returncode == 0 and len(record['outputs']) == 2 else 'failed'
record['finished'] = time.time()
provenance.write_text(json.dumps(record, indent=2) + '\n')
if record['status'] != 'ok':
    raise SystemExit('Conversion failed or shard count changed; see conversion.json')
print(json.dumps(record, indent=2))
