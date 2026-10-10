#!/usr/bin/env python3
"""Summarize sampled package power, temperature, memory and SMI counter deltas."""
import argparse
import json
from pathlib import Path
import re
import statistics

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
a = p.parse_args()
output = {}
for path in sorted(a.directory.glob('*/result.json')):
    result = json.loads(path.read_text())
    telemetry = json.loads(path.with_name('telemetry.json').read_text())
    values = {}
    for sample in telemetry:
        for key, name in sample.items():
            if key.endswith('/name') and name in ('amdgpu', 'k10temp'):
                base = key[:-4]
                for field, scale, label in (('temp1_input', 1000, 'temperature_c'),
                                             ('power1_average', 1e6, 'package_power_w')):
                    raw = sample.get(base + field)
                    if raw is not None:
                        values.setdefault(name + '_' + label, []).append(float(raw) / scale)
        match = re.search(r'MemAvailable:\s+(\d+) kB', sample.get('/proc/meminfo', ''))
        if match:
            values.setdefault('available_ram_gib', []).append(int(match[1]) / 1024**2)
        for key, value in sample.items():
            for field in ('vram', 'gtt'):
                if key.endswith('/mem_info_' + field + '_used'):
                    values.setdefault(field + '_used_gib', []).append(int(value) / 1024**3)
    summary = {key: {'minimum': min(v), 'median': statistics.median(v), 'maximum': max(v)}
               for key, v in values.items()}
    before, after = result.get('smi_before'), result.get('smi_after')
    if before and after:
        start = before['gpu_data'][0]['throttle']
        end = after['gpu_data'][0]['throttle']
        summary['raw_apu_throttle_counter_deltas'] = {
            key: end[key] - value for key, value in start.items()
            if key.startswith('apu_throttle_residency_') and isinstance(value, (int, float))
            and isinstance(end.get(key), (int, float))}
    summary['sampling_scope'] = 'Entire server lifecycle including model load, warmup and cleanup'
    output[path.parent.name] = summary
print(json.dumps(output, indent=2))
