#!/usr/bin/env python3
"""Summarize raw campaign results; bootstrap paired case improvements by workload."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
import statistics


def quantile(values, fraction):
    values = sorted(values)
    pos = (len(values) - 1) * fraction
    lower = int(pos)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (pos - lower)


def decode_tps(request):
    # The pinned ROCmFPX branch includes token one in its reported rate although
    # generation timing starts after that token. Normalize all branches equally.
    timings = request['timings']
    return max(0, timings['predicted_n'] - 1) / (timings['predicted_ms'] / 1000)


def summarize(case):
    groups = {}
    for batch in case['rows']:
        label = json.dumps(batch['workload'], sort_keys=True)
        groups.setdefault(label, []).append(batch)
    result = {}
    for label, batches in groups.items():
        rows = [r for b in batches for r in b['requests']]
        elapsed = sum(b['wall_seconds'] for b in batches)
        intervals = [t - previous for r in rows for previous, t in zip(
            r.get('token_arrival_seconds', []), r.get('token_arrival_seconds', [])[1:])]
        fairness = []
        energy_joules = []
        accepted_tokens, verification_steps = 0, 0
        for batch in batches:
            rates = [r['tokens_predicted'] / r['elapsed_seconds'] for r in batch['requests']]
            fairness.append(sum(rates) ** 2 / (len(rates) * sum(x * x for x in rates)))
            a, b = batch.get('metrics_before', {}), batch.get('metrics_after', {})
            accepted_key = 'llamacpp:spec_decode_num_accepted_tokens_total'
            steps_key = 'llamacpp:spec_decode_num_drafts_total'
            if accepted_key in a and steps_key in a and accepted_key in b and steps_key in b:
                accepted_tokens += b[accepted_key] - a[accepted_key]
                verification_steps += b[steps_key] - a[steps_key]
            before, after = batch.get('energy_before', {}), batch.get('energy_after', {})
            if before and before.keys() == after.keys():
                energy_joules.append(sum((after[path]['energy_uj'] - start['energy_uj']) %
                                         start['max_energy_range_uj'] for path, start in before.items()) / 1e6)
        result[label] = {
            'requests': len(rows), 'batches': len(batches),
            'input_tokens_range': [min(r['input_tokens'] for r in rows), max(r['input_tokens'] for r in rows)],
            'output_tokens_range': [min(r['tokens_predicted'] for r in rows), max(r['tokens_predicted'] for r in rows)],
            'stop_types': dict(Counter(r['stop_type'] for r in rows)),
            'aggregate_output_tps': sum(r['tokens_predicted'] for r in rows) / elapsed,
            'decode_tps_median': statistics.median(decode_tps(r) for r in rows),
            'ttft_p50': statistics.median(r['ttft_seconds'] for r in rows),
            'ttft_p95': quantile([r['ttft_seconds'] for r in rows], .95),
            'completion_p50': statistics.median(r['elapsed_seconds'] for r in rows),
            'completion_p95': quantile([r['elapsed_seconds'] for r in rows], .95),
            'observed_token_interval_p50': statistics.median(intervals) if intervals else None,
            'observed_token_interval_p95': quantile(intervals, .95) if intervals else None,
            'jain_request_rate_fairness_min': min(fairness),
            'package_energy_joules': sum(energy_joules) if len(energy_joules) == len(batches) else None,
            'accepted_tokens_per_verification': accepted_tokens / verification_steps if verification_steps else None,
            'correctness_failures': sum(r.get('correct') is False for r in rows),
            'cached_tokens': [r['timings'].get('cache_n') for r in rows],
            'draft_acceptance': sum(r['timings'].get('draft_n_accepted', 0) for r in rows) / max(1, sum(r['timings'].get('draft_n', 0) for r in rows)),
        }
    return result


def paired_interval(baseline, candidate, seed=1234, metric='throughput'):
    """Ratios are grouped by matched workload/repetition, not independent requests."""
    def extract(case):
        rows = {(json.dumps(b['workload'], sort_keys=True), b['repeat']): b for b in case['rows']}
        if len(rows) != len(case['rows']):
            raise ValueError('Duplicate paired workload/repetition')
        return rows
    a, b = extract(baseline), extract(candidate)
    if a.keys() != b.keys():
        raise ValueError('Paired workloads/repetitions differ')
    blocks = {}
    for key in a:
        ar, br = a[key], b[key]
        if len(ar['requests']) != len(br['requests']):
            raise ValueError('Paired cases have different client counts')
        if metric == 'throughput':
            at = sum(r['tokens_predicted'] for r in ar['requests']) / ar['wall_seconds']
            bt = sum(r['tokens_predicted'] for r in br['requests']) / br['wall_seconds']
        elif metric == 'decode':
            at, bt = [statistics.mean(decode_tps(r) for r in batch['requests']) for batch in (ar, br)]
        else:
            field = {'ttft': 'ttft_seconds', 'completion': 'elapsed_seconds'}[metric]
            # Reciprocal latency: a positive ratio consistently means improvement.
            at, bt = [1 / statistics.mean(r[field] for r in batch['requests']) for batch in (ar, br)]
        blocks.setdefault(key[1], []).append(math.log(bt / at))
    ratios = [statistics.mean(values) for values in blocks.values()]
    def improvement(log_ratio):
        return 1 - math.exp(-log_ratio) if metric in ('ttft', 'completion') else math.exp(log_ratio) - 1
    rng = random.Random(seed)
    boot = [improvement(statistics.mean(rng.choices(ratios, k=len(ratios)))) for _ in range(10000)]
    return {'metric': metric, 'geometric_mean_improvement': improvement(statistics.mean(ratios)),
            'ci95': [quantile(boot, .025), quantile(boot, .975)], 'paired_blocks': len(ratios)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--baseline')
    parser.add_argument('--candidate')
    parser.add_argument('--metric', choices=['throughput', 'decode', 'ttft', 'completion'], default='throughput')
    parser.add_argument('--secondary', choices=['ttft', 'completion'], default='completion')
    args = parser.parse_args()
    cases = {}
    for path in args.directory.glob('*/result.json'):
        data = json.loads(path.read_text())
        cases[path.parent.name] = data
    output = {name: {'status': data['status'], 'summary': summarize(data)} for name, data in cases.items()}
    if args.baseline and args.candidate:
        def group(name):
            if name in cases:
                if cases[name]['status'] != 'ok':
                    raise ValueError('Incomplete paired case: ' + name)
                return cases[name]
            rows = []
            for label, case in cases.items():
                if label.startswith(name + '-pair'):
                    if case['status'] != 'ok':
                        raise ValueError('Incomplete paired case: ' + label)
                    for row in case['rows']:
                        rows.append(row | {'repeat': case['spec']['pair_index']})
            if not rows:
                raise ValueError('No cases for ' + name)
            return {'rows': rows}
        baseline, candidate = group(args.baseline), group(args.candidate)
        comparison = paired_interval(baseline, candidate, metric=args.metric)
        field = {'ttft': 'ttft_seconds', 'completion': 'elapsed_seconds'}[args.secondary]
        p95s = [quantile([r[field] for batch in case['rows'] for r in batch['requests']], .95)
                for case in (baseline, candidate)]
        comparison['secondary_p95'] = {'metric': args.secondary, 'baseline': p95s[0], 'candidate': p95s[1],
                                       'relative_regression': p95s[1] / p95s[0] - 1}
        comparison['performance_gate_passed'] = (comparison['paired_blocks'] == 10 and
            comparison['geometric_mean_improvement'] >= .05 and comparison['ci95'][0] > 0 and
            p95s[1] / p95s[0] <= 1.05)
        output['paired_comparison'] = comparison
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
