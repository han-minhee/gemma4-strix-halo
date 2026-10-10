# Data

| File | Contents |
|---|---|
| `metrics.json` | Chart inputs and aggregates |
| `request-metrics.json` | 86 cases; requests, settings, statuses |
| `provenance.json` | Original artifact hashes |
| `software.json` | Software/package versions |

No responses or credentials. Charts exclude failures. Initial/campaign batches are separate.

[Runtime/model pins](../versions.json) · [Experimental source pins](../experiments/sources.json)

## Charts

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-charts.txt
.venv/bin/python tools/render_charts.py
```
