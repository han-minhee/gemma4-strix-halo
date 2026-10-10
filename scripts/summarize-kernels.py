#!/usr/bin/env python3
"""Extract operation costs from the retained, instrumented kernel profile."""
import argparse
import csv
import json
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
a = p.parse_args()
result = {'warning': 'Instrumented costs mix warmup and measured calls; not throughput promotion evidence.',
          'vulkan': {}, 'hip': []}
for depth in (4, 8):
    log = (a.directory / f'vulkan-{depth}' / f'mtp{depth}.log').read_text()
    cumulative = [float(x) for x in re.findall(r'dur\(b,g,a\) = [\d.]+, ([\d.]+),', log)]
    if len(cumulative) != 6:
        raise ValueError('Expected one warmup and one measured request for each of three prompts')
    operations = [line for line in log.splitlines()
                  if line.startswith('MUL_MAT') and '21504' in line and '5376' in line]
    result['vulkan'][str(depth)] = {
        'drafting_ms_prose_code_korean': [cumulative[i] - cumulative[i-1] for i in (1, 3, 5)],
        'ffn_operations': operations,
    }
paths = list((a.directory / 'hip').glob('*/*_kernel_stats.csv'))
if len(paths) != 1:
    raise ValueError('Expected exactly one HIP kernel stats file')
with paths[0].open() as handle:
    result['hip'] = list(csv.DictReader(handle))[:10]
print(json.dumps(result, indent=2))
