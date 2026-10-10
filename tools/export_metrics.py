#!/usr/bin/env python3
"""Export numeric evidence from private run directories; omit response text and telemetry."""
import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, p):
    values = sorted(values)
    pos = (len(values) - 1) * p
    i = int(pos)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (pos - i)


def stats(requests, wall=None):
    return {
        'requests': len(requests),
        'median_decode_tps': statistics.median(
            (r['timings']['predicted_n'] - 1) / (r['timings']['predicted_ms'] / 1000)
            for r in requests),
        'aggregate_decode_tps': sum(r['timings']['predicted_n'] - 1 for r in requests)
            / sum(r['timings']['predicted_ms'] / 1000 for r in requests),
        'aggregate_wall_tps': sum(r['tokens_predicted'] for r in requests) / (
            wall if wall is not None else sum(r['elapsed_seconds'] for r in requests)),
        'ttft_p50_s': statistics.median(r['ttft_seconds'] for r in requests),
        'ttft_p95_s': percentile([r['ttft_seconds'] for r in requests], .95),
        'completion_p50_s': statistics.median(r['elapsed_seconds'] for r in requests),
        'completion_p95_s': percentile([r['elapsed_seconds'] for r in requests], .95),
    }


def numeric_request(r):
    fields = ['prompt', 'repeat', 'input_tokens', 'ttft_seconds', 'elapsed_seconds',
              'timings', 'tokens_predicted', 'stop_type', 'truncated', 'correct', 'slot']
    out = {k: r[k] for k in fields if k in r}
    if 'text' in r:
        out['output_sha256'] = hashlib.sha256(r['text'].encode()).hexdigest()
    return out


def load(path, sources, label):
    sources[label] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial', required=True, type=Path)
    parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    sources, evidence, metrics = {}, {}, {'measured_date': '2026-10-10', 'status': 'paused'}
    initial = {}
    for label, file in [('deployed', 'http-container.json'), ('plain-vulkan', 'http-vulkan/baseline.json')]:
        rows = load(args.initial / file, sources, 'initial/' + label)
        evidence['initial/' + label] = [numeric_request(r) for r in rows]
        initial[label] = stats(rows)
        initial[label]['workloads'] = {
            prompt: stats([r for r in rows if r['prompt'] == prompt])
            for prompt in sorted({r['prompt'] for r in rows})}
    metrics['initial'] = initial
    depth = load(args.campaign / 'depth-summary.json', sources, 'depth-summary')
    metrics['depth'] = [{k: r[k] for k in ('case', 'median_tps', 'aggregate_tps', 'acceptance')} for r in depth]
    groups = ['target-quants-results', 'long-context-results', 'concurrency-results',
              'cpu-results', 'runtime-results', 'draft-precision-results', 'low-columns-results',
              'rocmfp4-plain-results']
    for group in groups:
        metrics[group] = {}
        for path in sorted((args.campaign / group).glob('*/result.json')):
            label = group + '/' + path.parent.name
            case = load(path, sources, label)
            out = {k: case[k] for k in ['status', 'identity', 'harness_hashes'] if k in case}
            # Public commands use documented example installation paths, never credentials.
            out['spec'] = {k: v for k, v in case.get('spec', {}).items() if k != 'key_file'}
            command = case.get('command', [])[:]
            if '--api-key-file' in command:
                command[command.index('--api-key-file') + 1] = '<PRIVATE_API_KEY_FILE>'
            out['command'] = command
            out['rows'] = [{k: b[k] for k in ['workload', 'repeat', 'wall_seconds']} |
                           {'requests': [numeric_request(r) for r in b['requests']]}
                           for b in case.get('rows', [])]
            evidence[label] = out
            summary = {'status': case.get('status'), 'workloads': []}
            if case.get('status') == 'ok' and case.get('rows'):
                rows = [r for b in case['rows'] for r in b['requests']]
                summary.update(stats(rows, sum(b['wall_seconds'] for b in case['rows'])))
                for workload in {json.dumps(b['workload'], sort_keys=True) for b in case['rows']}:
                    batches = [b for b in case['rows'] if json.dumps(b['workload'], sort_keys=True) == workload]
                    rs = [r for b in batches for r in b['requests']]
                    summary['workloads'].append({'workload': json.loads(workload),
                        **stats(rs, sum(b['wall_seconds'] for b in batches)),
                        'correctness_failures': sum(r.get('correct') is False for r in rs)})
                summary['workloads'].sort(key=lambda x: json.dumps(x['workload'], sort_keys=True))
            metrics[group][path.parent.name] = summary
    trace = load(args.campaign / 'kernel-profile-summary.json', sources, 'kernel-profile-summary')
    operations, durations = [], []
    for depth, columns in [('4', 5), ('8', 9)]:
        line = next(x for x in trace['vulkan'][depth]['ffn_operations']
                    if f'q4_K m=21504 n={columns} k=5376:' in x)
        operations.append(line.split()[0])
        durations.append(float(re.search(r'x ([0-9.]+) us', line)[1]))
    metrics['kernel'] = {'verification_columns': [5, 9], 'duration_us': durations, 'operations': operations}
    evidence['kernel-profile'] = trace
    for name, data in [('metrics.json', metrics), ('request-metrics.json', evidence), ('provenance.json', sources)]:
        (ROOT / 'data' / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(f'Exported {len(evidence) - 1} cases plus kernel summary; response text, API keys and telemetry omitted.')


if __name__ == '__main__':
    main()
