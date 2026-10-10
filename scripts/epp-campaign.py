#!/usr/bin/env python3
"""Compare a temporary EPP change, restoring every policy in a finally block.

Run as the ordinary benchmark operator under the experiment lock with production
stopped. Only sysfs writes use sudo; the benchmark keeps its usual UID and cache.
This wrapper does not change platform profile, suspend or persistent settings.
"""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import time


def write_preference(path, value):
    subprocess.run(['sudo', '-n', 'tee', str(path)], input=value, text=True,
                   stdout=subprocess.DEVNULL, check=True, timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    policies = sorted(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/energy_performance_preference'))
    saved = {str(path): path.read_text().strip() for path in policies}
    if not saved:
        raise RuntimeError('EPP controls unavailable')
    for path in policies:
        if 'performance' not in path.with_name('energy_performance_available_preferences').read_text().split():
            raise RuntimeError('Performance EPP unsupported: ' + str(path))
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = args.output / 'epp-restore.json'
    snapshot.write_text(json.dumps({'saved': saved, 'started': time.time()}, indent=2))
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    child = None
    try:
        for path in policies:
            write_preference(path, 'performance')
            if path.read_text().strip() != 'performance':
                raise RuntimeError('EPP readback failed: ' + str(path))
        child = subprocess.Popen(['python3', str(Path(__file__).with_name('campaign.py')), str(args.manifest),
                                  '--output', str(args.output / 'cases')], start_new_session=True)
        if child.wait() != 0:
            raise RuntimeError('EPP campaign process failed')
    finally:
        errors = []
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                errors.append({'process': child.pid, 'error': 'Campaign cleanup still running after SIGTERM'})
        for name, value in saved.items():
            try:
                path = Path(name)
                write_preference(path, value)
                if path.read_text().strip() != value:
                    raise RuntimeError('Readback mismatch')
            except Exception as error:
                errors.append({'path': name, 'error': str(error)})
        snapshot.write_text(json.dumps({'saved': saved, 'restored': not errors,
                                       'errors': errors, 'finished': time.time()}, indent=2))
        if errors:
            raise RuntimeError('EPP restoration failed: see ' + str(snapshot))


if __name__ == '__main__':
    main()
