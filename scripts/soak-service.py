#!/usr/bin/env python3
"""Exercise a deployed preset continuously with authenticated streamed requests."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import threading
import time
from campaign import Client, HARNESS_HASHES, package_energy, smi_snapshot, write_json
from profile import sample

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--url', default='http://127.0.0.1:8080')
p.add_argument('--key-file', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--seconds', type=int, default=600)
p.add_argument('--clients', type=int, choices=(1, 2, 4), default=1)
a = p.parse_args()
if a.output.exists() or a.seconds <= 0:
    raise SystemExit('Choose a new output directory and positive duration')
a.output.mkdir(parents=True)
client = Client(a.url.rstrip('/'), a.key_file.read_text().strip())
props = client.json('/props')
if props['total_slots'] < a.clients:
    raise SystemExit('Preset has fewer serving slots than soak clients')
context = props['default_generation_settings']['n_ctx']
workloads = [
    {'prompt': 'prose', 'output_tokens': 512},
    {'prompt': 'code', 'output_tokens': 512},
    {'prompt': 'korean', 'output_tokens': 128},
    # Exercise the advertised long-context capacity, not just a short prompt
    # inside a large allocation; retain output and template headroom.
    {'prompt': 'retrieval', 'input_tokens': context - 1024, 'natural_eos': True},
    {'prompt': 'reasoning', 'thinking': True, 'output_tokens': 512},
    {'prompt': 'json', 'natural_eos': True},
]
result = {'status': 'running', 'started': time.time(), 'requested_seconds': a.seconds,
          'clients': a.clients, 'props': props, 'harness_hashes': HARNESS_HASHES,
          'soak_harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'smi_before': smi_snapshot(), 'rows': []}
stop, telemetry = threading.Event(), []
def monitor():
    while not stop.is_set():
        telemetry.append(sample())
        stop.wait(1)
thread = threading.Thread(target=monitor)
thread.start()
started = time.monotonic()
try:
    while time.monotonic() - started < a.seconds:
        selected = [workloads[(len(result['rows']) + slot) % len(workloads)] for slot in range(a.clients)]
        if a.clients > 1 and len(result['rows']) % len(workloads) == 3:
            selected = [workloads[3] | {'secret': f'HALO{314159 + 101 * slot}'} for slot in range(a.clients)]
        prepared = [client.prepare(workload) for workload in selected]
        barrier = threading.Barrier(a.clients)
        def request(slot):
            barrier.wait()
            return client.generate(prepared[slot], selected[slot], slot, False) | {'workload': selected[slot], 'slot': slot}
        energy_before = package_energy()
        batch_started = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.clients) as pool:
            rows = list(pool.map(request, range(a.clients)))
        batch = {'workloads': selected, 'requests': rows, 'wall_seconds': time.monotonic() - batch_started,
                 'energy_before': energy_before, 'energy_after': package_energy()}
        result['rows'].append(batch)
        write_json(a.output / 'result.json', result)
        if any(row.get('correct') is False for row in rows):
            raise RuntimeError('Structured-output or retrieval canary failed')
        for row in rows:
            own_secret = row['workload'].get('secret')
            if own_secret and any(workload.get('secret') and workload['secret'] != own_secret and
                                  workload['secret'] in row['text'] for workload in selected):
                raise RuntimeError('Concurrent retrieval leaked another slot value')
        if any(row['workload'].get('natural_eos') and row['stop_type'] != 'eos' for row in rows):
            raise RuntimeError('Natural-completion canary failed to reach EOS')
        for row in rows:
            if row['workload']['prompt'] == 'json':
                expected = {'name': 'halo', 'enabled': True, 'ports': [8080, 8081]}
                if json.loads(row['text']) != expected:
                    raise RuntimeError('Strict structured-output canary failed')
        print(len(result['rows']), [workload['prompt'] for workload in selected], round(batch['wall_seconds'], 3), flush=True)
    result['status'] = 'ok'
except BaseException as error:
    result['status'] = 'failed'
    result['error'] = str(error)
    raise
finally:
    stop.set()
    thread.join()
    result['elapsed_seconds'] = time.monotonic() - started
    result['finished'] = time.time()
    result['smi_after'] = smi_snapshot()
    write_json(a.output / 'telemetry.json', telemetry)
    write_json(a.output / 'result.json', result)
