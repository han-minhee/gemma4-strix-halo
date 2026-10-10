#!/usr/bin/env python3
"""Generate HumanEval solutions and execute tests in a restricted disposable container."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid
from campaign import Client, write_json


def evaluate(program, image):
    marker = 'HALO_TESTS_COMPLETED_' + uuid.uuid4().hex
    program += '\nprint(' + repr(marker) + ')\n'
    container = 'halo-eval-' + uuid.uuid4().hex
    command = ['sudo', '-n', 'docker', 'run', '--pull=never', '--init', '--name', container, '--rm', '-i', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--pids-limit', '64',
               '--memory', '256m', '--cpus', '1', '--user', '65534:65534',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--entrypoint', 'python3', image, '-I', '-']
    # Container-internal alarm bounds execution even if the client is interrupted.
    program = 'import signal\nsignal.alarm(10)\nexec(compile(' + repr(program) + ", 'candidate', 'exec'))\n"
    try:
        result = subprocess.run(command, input=program, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30)
        if result.returncode in (125, 126, 127):
            raise RuntimeError('Evaluator infrastructure failure: ' + result.stderr[-2000:])
        passed = result.returncode == 0 and marker in result.stdout.splitlines()
        error = result.stderr[-2000:]
        if result.returncode == 0 and not passed:
            error = 'Candidate exited before the test completion marker'
    except subprocess.TimeoutExpired:
        passed, error = False, 'evaluator timeout'
    finally:
        subprocess.run(['sudo', '-n', 'docker', 'rm', '-f', container], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
    return passed, error


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--tasks', type=Path, required=True)
    p.add_argument('--image', required=True, help='Pinned Python evaluator image ID')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'experiments/quality-data.json').read_text())
    expected = next(entry for entry in manifest['files'] if entry['file'] == 'HumanEval.jsonl')
    task_data = args.tasks.read_bytes()
    if hashlib.sha256(task_data).hexdigest() != expected['sha256']:
        raise SystemExit('HumanEval input integrity failure')
    if args.output.exists():
        raise SystemExit('Refuse to overwrite previous quality results')
    client = Client(args.url, args.key_file.read_text().strip())
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for line in task_data.decode().splitlines():
        task = json.loads(line)
        prompt = 'Implement the following Python function. Return the complete function and required imports in one Python code block, with no explanation.\n' + task['prompt']
        rendered = client.json('/apply-template', {'messages': [{'role': 'user', 'content': prompt}],
                               'chat_template_kwargs': {'enable_thinking': False}})['prompt']
        tokens = client.json('/tokenize', {'content': rendered, 'add_special': True})['tokens']
        response = client.generate(tokens, {'prompt': 'code', 'output_tokens': 1024, 'natural_eos': True}, 0, False)
        matches = re.findall(r'```(?:python)?\s*\n(.*?)```', response['text'], flags=re.S)
        code = '\n'.join(matches) if matches else response['text']
        program = code + '\n' + task['test'] + '\ncheck(' + task['entry_point'] + ')\n'
        passed, error = evaluate(program, args.image)
        rows.append({'task_id': task['task_id'], 'passed': passed, 'error': error, 'response': response})
        write_json(args.output, {'tasks': len(rows), 'passed': sum(r['passed'] for r in rows), 'rows': rows,
                                'tasks_sha256': expected['sha256'], 'evaluator_image': args.image,
                                'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        print(task['task_id'], passed, flush=True)


if __name__ == '__main__':
    main()
