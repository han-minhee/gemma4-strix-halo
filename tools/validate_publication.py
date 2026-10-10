#!/usr/bin/env python3
"""Check published numeric aggregates, local documentation links, and excluded fields."""
import json
import math
import re
from pathlib import Path
from export_metrics import stats

ROOT = Path(__file__).resolve().parents[1]
metrics = json.loads((ROOT / 'data/metrics.json').read_text())
evidence = json.loads((ROOT / 'data/request-metrics.json').read_text())
count = 0
for label, case in evidence.items():
    if label == 'kernel-profile':
        continue
    if label.startswith('initial/'):
        expected = metrics['initial'][label.split('/')[1]]
        calculated = stats(case)
    elif case.get('status') == 'ok':
        group, name = label.split('/')
        rows = [r for b in case['rows'] for r in b['requests']]
        calculated = stats(rows, sum(b['wall_seconds'] for b in case['rows']))
        expected = metrics[group][name]
    else:
        continue
    for key, value in calculated.items():
        assert math.isclose(expected[key], value, rel_tol=1e-10), (label, key)
    count += 1


def inspect(value):
    if isinstance(value, dict):
        assert not ({'text', 'key_file', 'api_key', 'smi_before', 'smi_after'} & value.keys())
        for item in value.values(): inspect(item)
    elif isinstance(value, list):
        for item in value: inspect(item)


inspect(evidence)
links = 0
for file in ROOT.rglob('*.md'):
    if '.venv' in file.parts or '.chart-venv' in file.parts: continue
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', file.read_text()):
        if '://' in target or target.startswith('#'): continue
        assert (file.parent / target.split('#')[0]).exists(), (file, target)
        links += 1
for file in ROOT.glob('assets/*.svg'):
    import xml.etree.ElementTree as ET
    ET.parse(file)
print(f'Validated {count} successful case aggregates, {links} local links, all SVGs, and excluded private fields.')
