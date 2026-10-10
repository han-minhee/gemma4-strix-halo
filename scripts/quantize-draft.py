#!/usr/bin/env python3
"""Create assistant-only four-bit experiments from verified BF16 weights."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--models', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True, help='Conversion logs and provenance directory')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
entry = json.loads((root / 'versions.json').read_text())['files']['MTP_BF16']
source = args.models / Path(entry['path']).name
with source.open('rb') as handle:
    digest = hashlib.file_digest(handle, 'sha256').hexdigest()
if source.stat().st_size != entry['size'] or digest != entry['sha256']:
    raise SystemExit('BF16 assistant integrity verification failed')
args.output.mkdir(parents=True, exist_ok=True)
with args.binary.open('rb') as handle:
    binary_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
records = []
for quant in ('Q4_0', 'Q4_K_M'):
    target = args.models / ('mtp-gemma-4-31B-it-' + quant + '.gguf')
    partial = target.with_suffix('.gguf.part')
    if target.exists() or partial.exists():
        raise SystemExit('Refuse to overwrite an existing conversion: ' + str(target))
    command = [str(args.binary), str(source), str(partial), quant, '8']
    with (args.output / (quant + '.log')).open('w') as log:
        subprocess.run(command, stdout=log, stderr=log, check=True)
    with partial.open('rb') as handle:
        output_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
    partial.rename(target)
    records.append({'command': command, 'quantizer_sha256': binary_hash, 'source_sha256': digest, 'output_sha256': output_hash,
                    'output': str(target), 'bytes': target.stat().st_size})
    (args.output / 'conversions.json').write_text(json.dumps(records, indent=2))
    print('Converted', quant, target.stat().st_size, output_hash, flush=True)
