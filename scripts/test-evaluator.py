#!/usr/bin/env python3
"""Check evaluator success, early exit, assertion failure and execution bounds."""
import argparse
import json
import time
from quality_eval import evaluate

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--image', required=True)
a = p.parse_args()
results = []
fixtures = [
    ('ordinary_success', 'import os\nassert os.getuid() == 65534\nassert 6 * 7 == 42', True),
    ('early_exit', 'import sys\nsys.exit(0)', False),
    ('failed_assertion', 'assert 6 * 7 == 41', False),
    ('bounded_execution', 'while True:\n    pass', False),
]
for name, program, expected in fixtures:
    started = time.monotonic()
    passed, error = evaluate(program, a.image)
    elapsed = time.monotonic() - started
    correct = passed == expected and elapsed < (20 if name == 'bounded_execution' else 35)
    results.append({'fixture': name, 'passed': correct, 'seconds': elapsed, 'evaluation_error': error})
print(json.dumps(results, indent=2))
if not all(row['passed'] for row in results):
    raise SystemExit('Evaluator validation failed')
