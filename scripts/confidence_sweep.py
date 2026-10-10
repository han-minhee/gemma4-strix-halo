#!/usr/bin/env python3
"""Select three screened depths and run the predeclared confidence matrix."""
import argparse
import json
from pathlib import Path
import random
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('experiment',type=Path)
a=p.parse_args()
scores=[]
for f in (a.experiment/'depth').glob('*.meta.json'):
 if json.loads(f.read_text())['status'] != 0: continue
 name=f.name.removesuffix('.meta.json');rows=json.loads((f.parent/(name+'.json')).read_text())
 scores.append((sum(r['timings']['predicted_n']-1 for r in rows)/sum(r['timings']['predicted_ms']/1000 for r in rows),name))
selected=[n for _,n in sorted(scores,reverse=True)[:3]]
if len(scores)!=8: raise SystemExit('All eight depth screens must finish first')
cases=[f'{n}-p{p}' for n in selected for p in [.5,.7,.8,.9]]
cases += [f'mtp{n}-p{p}' for n in [12,16] for p in [.7,.9]]
random.Random(20261010).shuffle(cases)
cases=['mtp4@before']+cases+['mtp4@after']
(a.experiment/'confidence-selection.json').write_text(json.dumps({'scores':scores,'selected':selected,'cases':cases},indent=2))
command=['python3',str(Path(__file__).with_name('server_sweep.py')),'--binary','/srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-server','--model','/srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf','--draft','/srv/amd-halo/models/mtp-gemma-4-31B-it-Q8_0.gguf','--key-file','/srv/amd-halo/secrets/api-key','--output',str(a.experiment/'confidence'),'--cases',*cases,'--','--n-gpu-layers','999','--threads','2','--threads-batch','2','--ctx-size','8192','--batch-size','2048','--ubatch-size','512','--flash-attn','on','--cache-type-k','f16','--cache-type-v','f16','--load-mode','none']
subprocess.run(command,check=True)
