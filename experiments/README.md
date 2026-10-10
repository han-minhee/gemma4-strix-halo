# Harness

Reference: `/srv/amd-halo/stack`. Lock: `/srv/amd-halo/experiments/benchmark.lock`.

Copy `scripts/`, `experiments/`, `patches/`, and `versions.json` into an isolated directory. The wrapper stops/restores Compose.

```sh
bash scripts/run-campaign.sh experiments/long-context.json context-results
python3 scripts/analyze-campaign.py context-results
```

One GPU workload at a time. Fresh directories for incomplete runs. Nonempty numerical tests; upstream tolerances.

Thermal stabilization needs repair before paired validation. Coding evaluation requires the evaluator image ID. No automatic promotion.

[Setup](../docs/setup.md) · [Metrics](../docs/methodology.md)
