# Published measurements

| File | Contents |
|---|---|
| `metrics.json` | Chart inputs and per-case aggregates |
| `request-metrics.json` | 86 case exports plus kernel trace summary: numeric requests, settings, commands, statuses, output hashes |
| `provenance.json` | SHA256 of original input artifacts |

Response text, API-key contents, host telemetry, private operator environments, and model weights are excluded. Command credential arguments are replaced by a placeholder. Failed cases remain in the export and are excluded from charts.

`tools/export_metrics.py` regenerates these files from the original initial and campaign result directories. `tools/render_charts.py` renders all PNG/SVG figures from `metrics.json`. Initial deployment and later campaign measurements are separate batches; do not treat them as paired experiments.

Source snapshot: `a15f821` from the local optimization worktree. Runtime and model pins: [`versions.json`](../versions.json). Experimental source commits: [`experiments/sources.json`](../experiments/sources.json). Original artifact hashes describe the measured harness; publication edits do not change those historical identities.
