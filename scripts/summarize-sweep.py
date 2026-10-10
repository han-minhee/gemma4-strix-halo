#!/usr/bin/env python3
"""Summarize server_sweep outputs without combining warm and timed requests."""
import argparse
import json
from pathlib import Path
import re
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path)
parser.add_argument('--repetitions', type=int, default=3)
args = parser.parse_args()
output = []
for path in args.directory.glob('*.meta.json'):
    name = path.name.removesuffix('.meta.json')
    metadata = json.loads(path.read_text())
    row = {'case': name, 'status': metadata['status']}
    if metadata['status'] == 0:
        requests = json.loads((args.directory / (name + '.json')).read_text())
        log = (args.directory / (name + '.log')).read_text()
        lengths = [float(x) for x in re.findall(r'mean len =\s*([0-9.]+)', log)]
        accepted = [value - 1 for i, value in enumerate(lengths) if i % (args.repetitions + 1)]
        if lengths and len(accepted) != len(requests):
            raise ValueError('Server statistics do not match timed request count: ' + name)
        row.update(
            median_tps=statistics.median(r['timings']['predicted_per_second'] for r in requests),
            aggregate_tps=sum(r['timings']['predicted_n'] - 1 for r in requests) /
                          sum(r['timings']['predicted_ms'] / 1000 for r in requests),
            ttft_p50=statistics.median(r['ttft_seconds'] for r in requests),
            acceptance=sum(r['timings'].get('draft_n_accepted', 0) for r in requests) /
                       max(1, sum(r['timings'].get('draft_n', 0) for r in requests)),
            accepted_tokens_per_verification_per_request=accepted,
        )
    output.append(row)
output.sort(key=lambda row: row.get('aggregate_tps', 0), reverse=True)
print(json.dumps(output, indent=2))
