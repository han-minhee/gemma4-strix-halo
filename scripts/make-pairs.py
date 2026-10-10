#!/usr/bin/env python3
"""Construct ten adjacent randomized reference/candidate pairs from explicit specs."""
import argparse,json,random
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--common',type=Path,required=True)
p.add_argument('--reference',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
common=json.loads(a.common.read_text()); common['repetitions']=1
common['thermal_stabilization']=True
common['measure_energy']=True
common.setdefault('thermal_workload', common['workloads'][0] | {'reuse': False})
specs={'reference':json.loads(a.reference.read_text()),'candidate':json.loads(a.candidate.read_text())}
rng=random.Random(20261010);cases=[]
for pair in range(10):
 order=['reference','candidate'];rng.shuffle(order)
 for arm in order:cases.append(specs[arm]|{'name':f'{arm}-pair{pair:02d}','pair_index':pair})
a.output.write_text(json.dumps({'common':common,'cases':cases},indent=2)+'\n')
