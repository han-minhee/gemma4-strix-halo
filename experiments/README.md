# Experimental harness

Manifests use example host paths under `/srv/amd-halo`. They are screening configurations, not qualified deployment presets. Adjust paths before use; preserve the original stack at `/srv/amd-halo/stack`.

Copy `scripts/`, `experiments/`, `patches/`, and `versions.json` into an isolated experiment directory. The wrapper takes `/srv/amd-halo/experiments/benchmark.lock`, stops the reference service, and restores it on exit.

```sh
bash scripts/run-campaign.sh experiments/long-context.json context-results
python3 scripts/analyze-campaign.py context-results
```

Run only one GPU workload at a time. Use fresh result directories for incomplete cases. Numerical tests must execute nonempty case selections and retain upstream tolerances.

Ten-pair finalist manifests can be generated with `scripts/make-pairs.py`. The current thermal plateau criterion failed on workload temperature cycles and needs review before final paired use. `screen-final-candidates.sh` queues unfinished stages; do not interpret its existence as completed validation.

Quality tools cover fixed bilingual perplexity, restricted-container HumanEval, and strict JSON/retrieval canaries. The coding evaluator requires its immutable container image ID. No script promotes a candidate automatically.

See [methodology](../docs/methodology.md), [experiment findings](../docs/experiments.md), and [setup / rollback](../docs/setup.md).
