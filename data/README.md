# Data

| File | Contents |
|---|---|
| `metrics.json` | Chart inputs and aggregates |
| `request-metrics.json` | 86 cases: numeric requests, settings, statuses, output hashes |
| `provenance.json` | Original artifact hashes |
| `software.json` | Software versions and package records |

Response text and credentials are excluded. Failed cases are retained but omitted from charts. Initial and campaign results are separate batches.

[Runtime/model pins](../versions.json) · [Experimental source pins](../experiments/sources.json)

## Charts

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-charts.txt
.venv/bin/python tools/render_charts.py
```
