#!/usr/bin/env python3
"""Run a resumable serial experiment manifest against isolated native servers."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import socket
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from profile import sample
from http_profile import PROMPTS

HARNESS_HASHES = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                  for name in ('campaign.py', 'profile.py', 'http_profile.py')}

PROMPTS = PROMPTS | {
    'json': 'Return only valid JSON, without a code fence, with name "halo", enabled true, and ports [8080, 8081].',
    'reasoning': 'A train travels 120 km at 60 km/h and returns at 40 km/h. Derive the average speed across the entire journey.',
    'retrieval': 'Return the exact secret value from the document and nothing else.',
    'conversation': 'Based on your explanation, give two concrete ways to reduce memory traffic during inference.',
    'conversation_start': 'Explain CPU and GPU unified memory in two sentences.',
}


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)


def package_energy():
    """Read package RAPL without changing its root-only file permissions."""
    readings = {}
    for path in Path('/sys/class/powercap').glob('intel-rapl:*/energy_uj'):
        if path.parent.name.count(':') != 1:
            continue  # Child domains overlap package energy; do not double count.
        try:
            value = subprocess.check_output(['sudo', '-n', 'cat', str(path)], stderr=subprocess.DEVNULL,
                                            timeout=3, text=True)
            readings[str(path)] = {'energy_uj': int(value),
                                  'max_energy_range_uj': int(path.with_name('max_energy_range_uj').read_text())}
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    return readings


def smi_snapshot():
    binary = '/srv/amd-halo/rocm-venv/bin/amd-smi'
    try:
        return json.loads(subprocess.check_output([binary, 'metric', '--power', '--temperature',
                                                  '--violation', '--json'], timeout=10, text=True,
                                                 stderr=subprocess.DEVNULL))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def thermal_plateau(readings, age, sensors):
    if age < 120:
        return False
    for sensor in sensors:
        recent = [r['temperatures_c'][sensor] for r in readings if age - 30 < r['elapsed'] <= age]
        previous = [r['temperatures_c'][sensor] for r in readings if age - 60 < r['elapsed'] <= age - 30]
        if (len(recent) < 20 or len(previous) < 20 or
                abs(statistics.mean(recent) - statistics.mean(previous)) > 1 or
                max(recent) - min(recent) > 3):
            return False
    return True


class Client:
    def __init__(self, url, key):
        self.url, self.headers = url, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}

    def open(self, path, data=None):
        request = urllib.request.Request(self.url + path, None if data is None else json.dumps(data).encode(), self.headers)
        return urllib.request.urlopen(request, timeout=1800)

    def json(self, path, data=None):
        with self.open(path, data) as response:
            return json.load(response)

    def metrics(self):
        with self.open('/metrics') as response:
            lines = response.read().decode().splitlines()
        result = {}
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            name, value = line.split()[:2]
            if ':spec_decode_' in name or name.endswith(':n_decode_total'):
                result[name] = float(value)
        return result

    def prepare(self, workload):
        kind = workload['prompt']
        content = PROMPTS[kind]
        target = workload.get('input_tokens', 0)
        secret = workload.get('secret', 'HALO314159')
        if target:
            # Tokenize first, then submit token IDs to retain the precise input length.
            document = '\n'.join(f'Record {i}: This document describes a local inference system. CPU and GPU share memory. 문서의 일반 정보입니다.' for i in range(target // 8 + 100))
            middle = len(document) // 2
            document = document[:middle] + f'\nThe secret value is {secret}.\n' + document[middle:]
            content = document + '\n' + content
        rendered = self.json('/apply-template', {'messages': [{'role': 'user', 'content': content}],
                             'chat_template_kwargs': {'enable_thinking': workload.get('thinking', False)}})['prompt']
        tokens = self.json('/tokenize', {'content': rendered, 'add_special': True})['tokens']
        if target and len(tokens) > target:
            # Preserve both template ends and put an explicit retrieval key inside retained tokens.
            needle = self.json('/tokenize', {'content': f'\nThe secret value is {secret}.\n', 'add_special': False})['tokens']
            prefix = tokens[:target - 128 - len(needle)]
            middle = len(prefix) // 2
            tokens = prefix[:middle] + needle + prefix[middle:] + tokens[-128:]
        if target and len(tokens) != target:
            raise RuntimeError('Prepared input length differs from requested token count')
        return tokens

    def generate(self, tokens, workload, slot, cache):
        payload = {'prompt': tokens, 'stream': True, 'n_predict': workload.get('output_tokens', 128),
                   'temperature': 0, 'seed': 1234, 'cache_prompt': cache,
                   'return_tokens': True,
                   'ignore_eos': not workload.get('natural_eos', False)}
        if slot is not None:
            payload['id_slot'] = slot
        started = time.monotonic()
        arrivals, token_arrivals, output, last = [], [], [], None
        with self.open('/completion', payload) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                data = line[6:].strip()
                if data == b'[DONE]':
                    continue
                event = json.loads(data)
                received = time.monotonic() - started
                if 'error' in event:
                    raise RuntimeError(str(event['error']))
                if event.get('content'):
                    arrivals.append(received)
                    output.append(event['content'])
                if not event.get('stop'):
                    token_arrivals.extend([received] * len(event.get('tokens', [])))
                if event.get('stop'):
                    last = event
        elapsed = time.monotonic() - started
        if last is None or not arrivals:
            raise RuntimeError('Incomplete or empty generation')
        text = ''.join(output)
        result = {'input_tokens': len(tokens), 'ttft_seconds': arrivals[0], 'elapsed_seconds': elapsed,
                  'chunk_arrival_seconds': arrivals, 'timings': last.get('timings', {}),
                  'token_arrival_seconds': token_arrivals,
                  'text': text, 'stop_type': last.get('stop_type'), 'truncated': last.get('truncated', False),
                  'tokens_predicted': last.get('tokens_predicted'), 'cache_requested': cache}
        if result['truncated']:
            raise RuntimeError('Prompt was truncated')
        if not workload.get('natural_eos', False) and result['tokens_predicted'] != payload['n_predict']:
            raise RuntimeError('Fixed-length generation returned an unexpected token count')
        if token_arrivals and len(token_arrivals) != result['tokens_predicted']:
            raise RuntimeError('Streaming token accounting differs from generation count')
        if not cache and result['timings'].get('cache_n') != 0:
            raise RuntimeError('Cold request has cached tokens or missing cache accounting')
        if workload['prompt'] == 'json' and workload.get('natural_eos'):
            try:
                value = json.loads(text)
                result['correct'] = value == {'name': 'halo', 'enabled': True, 'ports': [8080, 8081]}
            except ValueError:
                result['correct'] = False
        if workload['prompt'] == 'retrieval':
            result['correct'] = workload.get('secret', 'HALO314159') in text
        return result

    def conversation(self):
        initial = self.prepare({'prompt': 'conversation_start'})
        reply = self.generate(initial, {'prompt': 'conversation_start', 'output_tokens': 256, 'natural_eos': True}, 0, True)
        if reply['stop_type'] != 'eos':
            raise RuntimeError('Conversation priming response did not reach EOS')
        rendered = self.json('/apply-template', {'messages': [
            {'role': 'user', 'content': PROMPTS['conversation_start']},
            {'role': 'assistant', 'content': reply['text']},
            {'role': 'user', 'content': PROMPTS['conversation']}],
            'chat_template_kwargs': {'enable_thinking': False}})['prompt']
        return self.json('/tokenize', {'content': rendered, 'add_special': True})['tokens'], reply


def run_case(case, common, directory, key):
    name = case['name']
    destination = directory / name
    destination.mkdir(exist_ok=True)
    spec = common | case
    identity = hashlib.sha256(json.dumps({'spec': spec, 'harness': HARNESS_HASHES}, sort_keys=True).encode()).hexdigest()
    result_path = destination / 'result.json'
    if result_path.exists():
        old = json.loads(result_path.read_text())
        if old.get('identity') == identity and old.get('status') == 'ok':
            print(name, 'already complete', flush=True)
            return True
        raise RuntimeError(f'{name}: existing incomplete/different result; choose a new output directory')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    binary = spec['binary']
    command = spec.get('prefix', []) + [binary, '--model', spec['model'], '--host', '127.0.0.1', '--port', str(port),
               '--api-key-file', spec['key_file'], '--parallel', str(spec.get('slots', 1)),
               '--ctx-size', str(spec.get('context_per_slot', 8192) * spec.get('slots', 1)),
               '--n-gpu-layers', '999', '--threads', str(spec.get('threads', 2)), '--threads-batch', str(spec.get('threads_batch', 2)),
               '--batch-size', str(spec.get('batch', 2048)), '--ubatch-size', str(spec.get('ubatch', 512)),
               '--flash-attn', 'on', '--cache-type-k', spec.get('kv', 'f16'), '--cache-type-v', spec.get('kv', 'f16'),
               '--fit', 'off',
               *spec.get('load_flags', ['--load-mode', 'none']), '--metrics', *spec.get('flags', [])]
    if spec.get('depth', 4):
        command += ['--model-draft', spec['draft'], '--spec-type', spec.get('spec_type', 'draft-mtp'),
                    '--spec-draft-n-max', str(spec.get('depth', 4)), '--spec-draft-p-min', str(spec.get('p_min', 0))]
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ('LLAMA_ARG_', 'GGML_', 'RADV_', 'MESA_', 'HSA_', 'HIP_', 'ROCR_'))}
    env.update(spec.get('environment', {}))
    result = {'identity': identity, 'harness_hashes': HARNESS_HASHES, 'spec': spec, 'command': command,
              'started': time.time(), 'status': 'running', 'rows': []}
    write_json(result_path, result)
    stop, telemetry = threading.Event(), []
    def monitor():
        while not stop.is_set():
            telemetry.append(sample())
            stop.wait(1)
    thread = threading.Thread(target=monitor)
    process = None
    try:
        with (destination / 'server.log').open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
            thread.start()
            client = Client(f'http://127.0.0.1:{port}', key)
            deadline = time.monotonic() + 300
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f'Server exited: {process.returncode}')
                try:
                    if client.json('/health')['status'] == 'ok':
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError('Server readiness')
                time.sleep(1)
            properties = client.json('/props')
            result['effective_settings'] = {key: properties[key] for key in
                ('total_slots', 'default_generation_settings', 'model_path', 'build_info') if key in properties}
            if properties.get('total_slots') != spec.get('slots', 1):
                raise RuntimeError('Effective slot count differs from the requested configuration')
            if properties.get('default_generation_settings', {}).get('n_ctx') != spec.get('context_per_slot', 8192):
                raise RuntimeError('Effective per-slot context differs from the requested configuration')
            if spec.get('thermal_stabilization'):
                conditioning = spec.get('thermal_workload', {'prompt': 'prose', 'output_tokens': 128})
                conditioning_tokens = client.prepare(conditioning)
                conditioning_clients = conditioning.get('concurrency', spec['workloads'][0].get('concurrency', spec.get('slots', 1)))
                thermal_started, thermal_epoch = time.monotonic(), time.time()
                while True:
                    barrier = threading.Barrier(conditioning_clients)
                    def condition(slot):
                        barrier.wait()
                        selected = slot if conditioning_clients <= spec.get('slots', 1) else None
                        return client.generate(conditioning_tokens, conditioning, selected, False)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=conditioning_clients) as pool:
                        list(pool.map(condition, range(conditioning_clients)))
                    snapshot = sample()
                    sensors = [str(Path(path).parent / 'temp1_input') for path, value in snapshot.items()
                               if path.endswith('/name') and value in ('k10temp', 'amdgpu')]
                    if len(sensors) < 2 or any(sensor not in snapshot for sensor in sensors):
                        raise RuntimeError('APU CPU/GPU temperatures unavailable for thermal stabilization')
                    age = time.monotonic() - thermal_started
                    # Read the one-second monitor, including time inside long
                    # prefill requests. End-of-request samples alone leave
                    # empty 30-second windows for long-context conditioning.
                    readings = [{'elapsed': item['time'] - thermal_epoch,
                                 'temperatures_c': {s: int(item[s]) / 1000 for s in sensors}}
                                for item in list(telemetry) if item['time'] >= thermal_epoch and
                                all(s in item for s in sensors)]
                    stable = thermal_plateau(readings, age, sensors)
                    if stable or age >= 360:
                        result['thermal_conditioning'] = {'stable': bool(stable), 'readings': readings,
                                                          'clients': conditioning_clients, 'workload': conditioning}
                        write_json(result_path, result)
                        if not stable:
                            raise RuntimeError('Temperature did not stabilize within six minutes')
                        break
            result['smi_before'] = smi_snapshot()
            for workload in spec['workloads']:
                tokens = client.prepare(workload)
                concurrency = workload.get('concurrency', spec.get('slots', 1))
                for repeat in range(-1, spec.get('repetitions', 3)):
                    conversation_prime = None
                    if workload['prompt'] == 'conversation':
                        if concurrency != 1 or not workload.get('reuse'):
                            raise ValueError('Conversation checks require one client and prefix reuse')
                        tokens, conversation_prime = client.conversation()
                    # Every measured reused-prefix request has an explicit immediate priming request.
                    elif workload.get('reuse'):
                        for slot in range(concurrency):
                            client.generate(tokens, workload | {'output_tokens': 1}, slot, True)
                    barrier = threading.Barrier(concurrency)
                    def request(slot):
                        barrier.wait()
                        selected_slot = slot if concurrency <= spec.get('slots', 1) else None
                        return client.generate(tokens, workload, selected_slot, workload.get('reuse', False)) | {'slot': selected_slot}
                    energy_before = package_energy() if spec.get('measure_energy') else {}
                    metrics_before = client.metrics()
                    started = time.monotonic()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                        rows = list(pool.map(request, range(concurrency)))
                    wall = time.monotonic() - started
                    energy_after = package_energy() if spec.get('measure_energy') else {}
                    metrics_after = client.metrics()
                    if repeat >= 0:
                        if workload.get('reuse') and any(r['timings'].get('cache_n', 0) <= 0 for r in rows):
                            raise RuntimeError('Reused-prefix request reported no cache hits')
                        result['rows'].append({'workload': workload, 'repeat': repeat, 'wall_seconds': wall,
                                               'requests': rows, 'energy_before': energy_before, 'energy_after': energy_after})
                        result['rows'][-1].update(metrics_before=metrics_before, metrics_after=metrics_after)
                        if conversation_prime is not None:
                            result['rows'][-1]['conversation_prime'] = conversation_prime
                        write_json(result_path, result)
                    print(name, workload, repeat, round(wall, 3), flush=True)
            if spec.get('quality_tasks'):
                subprocess.run(['python3', str(Path(__file__).with_name('quality_eval.py')), '--url', client.url,
                                '--key-file', spec['key_file'], '--tasks', spec['quality_tasks'],
                                '--image', spec['eval_image'], '--output', str(destination / 'humaneval.json')],
                               check=True, timeout=14400)
            result['status'] = 'ok'
            result['smi_after'] = smi_snapshot()
    except Exception as error:
        result['status'] = 'failed'
        result['error'] = str(error)
        print(name, 'FAILED', error, flush=True)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        stop.set()
        if thread.ident:
            thread.join()
        write_json(destination / 'telemetry.json', telemetry)
        result['finished'] = time.time()
        if result['status'] == 'running':
            result['status'] = 'interrupted'
        write_json(result_path, result)
    return result['status'] == 'ok'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    spec = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    key = Path(spec['common']['key_file']).read_text().strip()
    cases = spec['cases']
    if spec.get('shuffle_seed') is not None:
        random.Random(spec['shuffle_seed']).shuffle(cases)
    outcomes = [run_case(case, spec['common'], args.output, key) for case in cases]
    if not all(outcomes):
        raise SystemExit('One or more campaign cases failed; inspect retained result.json files')


if __name__ == '__main__':
    main()
