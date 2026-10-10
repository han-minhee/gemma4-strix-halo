#!/usr/bin/env python3
"""Evaluate the approved quantization gates from retained quality artifacts."""
import argparse
import json
from pathlib import Path
import re
import shlex


def perplexity(directory, language):
    matches = []
    for path in directory.glob('*' + language + '*'):
        if path.is_file():
            matches.extend(re.findall(r'Final estimate: PPL = ([0-9.]+)', path.read_text(errors='replace')))
    if len(matches) != 1:
        raise ValueError(f'Expected one final {language} perplexity in {directory}, found {len(matches)}')
    return float(matches[0])


def ppl_provenance(directory, language, allow_kv_change=False):
    command = shlex.split((directory / (language + '.command')).read_text())
    model_index = command.index('-m')
    # Candidate backends/models may differ; every scoring option must match.
    options = command[1:model_index] + command[model_index + 2:]
    if allow_kv_change:
        for flag in ('--cache-type-k', '--cache-type-v'):
            index = options.index(flag)
            if options[index + 1] not in ('f16', 'q8_0', 'q4_0'):
                raise ValueError('Unsupported KV quantization')
            options[index + 1] = '<declared-kv-change>'
    checksums = {}
    for line in (directory / 'inputs.sha256').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        if Path(name).name in ('wikipedia-en.txt', 'wikipedia-ko.txt'):
            checksums[Path(name).name] = digest
    if len(checksums) != 2:
        raise ValueError('Missing perplexity corpus hashes')
    return options, checksums


def coding(path):
    data = json.loads(path.read_text())
    tasks = {row['task_id']: bool(row['passed']) for row in data['rows']}
    if len(tasks) != 164 or len(data['rows']) != 164:
        raise ValueError('HumanEval must contain all 164 unique tasks')
    metadata = {key: data[key] for key in ('tasks_sha256', 'evaluator_image', 'harness_sha256')}
    if any(not value for value in metadata.values()):
        raise ValueError('Missing coding provenance')
    return tasks, metadata


def canaries(path):
    data = json.loads(path.read_text())
    if data['status'] != 'ok':
        raise ValueError('Incomplete quality canaries')
    checks = {}
    for batch in data['rows']:
        if batch['workload']['prompt'] not in ('json', 'retrieval'):
            continue
        for i, row in enumerate(batch['requests']):
            key = (json.dumps(batch['workload'], sort_keys=True), batch['repeat'], i)
            if key in checks or 'correct' not in row:
                raise ValueError('Duplicate or unscored canary')
            passed = row['correct']
            if batch['workload']['prompt'] == 'json':
                try:
                    passed = passed and json.loads(row['text']) == {'name': 'halo', 'enabled': True, 'ports': [8080, 8081]}
                except (ValueError, KeyError):
                    passed = False
            checks[key] = bool(passed)
    if not checks or not all(any(kind in key[0] for key in checks) for kind in ('json', 'retrieval')):
        raise ValueError('Both JSON and retrieval checks are required')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True, help='Directory containing ppl/, humaneval.json, canaries.json')
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--allow-kv-change', action='store_true', help='Declare KV precision as an experimental factor; retain all scoring and corpus checks')
    args = parser.parse_args()
    result = {}
    for language in ('en', 'ko'):
        metadata = [ppl_provenance(root / 'ppl', language, args.allow_kv_change) for root in (args.baseline, args.candidate)]
        if metadata[0] != metadata[1]:
            raise ValueError('Perplexity corpus or scoring options differ')
        a, b = [perplexity(root / 'ppl', language) for root in (args.baseline, args.candidate)]
        result['ppl_' + language] = {'baseline': a, 'candidate': b, 'relative_increase': b / a - 1,
                                   'passed': b / a <= 1.01, 'kv_change_declared': args.allow_kv_change}
    (a, am), (b, bm) = [coding(root / 'humaneval.json') for root in (args.baseline, args.candidate)]
    if am != bm:
        raise ValueError('Coding dataset, evaluator image or harness differ')
    if a.keys() != b.keys():
        raise ValueError('Coding tasks differ')
    loss = (sum(a.values()) - sum(b.values())) / len(a)
    result['coding'] = {'baseline_passed': sum(a.values()), 'candidate_passed': sum(b.values()),
                        'tasks': len(a), 'loss_percentage_points': loss * 100, 'passed': loss <= .02}
    a, b = [canaries(root / 'canaries.json') for root in (args.baseline, args.candidate)]
    if a.keys() != b.keys():
        raise ValueError('Quality canaries differ')
    failures = [str(key) for key in a if a[key] and not b[key]]
    result['canaries'] = {'new_failures': failures, 'passed': not failures}
    result['passed'] = all(gate['passed'] for gate in result.values())
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
