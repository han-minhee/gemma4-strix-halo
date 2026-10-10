#!/usr/bin/env python3
"""Create isolated source checkouts with verified baseline kernel patches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('experiment', type=Path)
p.add_argument('names', nargs='+', choices=['threshold16', 'rows2', 'rows8', 'lowcols2', 'lowcols4', 'rocmfpx-gemma', 'rocmfpx-gemma-v2', 'hip-wide-fa'])
p.add_argument('--baseline', type=Path, default=Path('/srv/amd-halo/stack/.runtime/llama.cpp'))
a = p.parse_args()
sources = json.loads((a.experiment / 'experiments/sources.json').read_text())
for name in a.names:
    spec = sources[name]
    patch = a.experiment / spec['patch']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != spec['patch_sha256']:
        raise SystemExit('Patch integrity failure: ' + name)
    destination = a.experiment / 'sources' / name
    if destination.exists():
        raise SystemExit('Refuse to overwrite candidate: ' + str(destination))
    if name.startswith('rocmfpx-gemma'):
        source = a.experiment / 'sources/rocmfpx'
        if source.joinpath('SOURCE_PIN').read_text().strip() != spec['repository'] + ' ' + spec['commit']:
            raise SystemExit('ROCmFPX source pin mismatch')
        subprocess.run(['cp', '-a', '--reflink=auto', str(source), str(destination)], check=True)
    else:
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(a.baseline), str(destination)], check=True)
        subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', spec['commit']], check=True)
    subprocess.run(['git', '-C', str(destination), 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', '-C', str(destination), 'apply', str(patch)], check=True)
    (destination / 'SOURCE_PIN').write_text(json.dumps(spec, indent=2) + '\n')
    print(name, spec['commit'], spec['patch_sha256'], flush=True)
