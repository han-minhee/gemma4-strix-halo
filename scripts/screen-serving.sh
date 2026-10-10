#!/usr/bin/env bash
# Each batch restores and health-checks production before the next batch.
set -euo pipefail
e=${1:?experiment directory}
cd "$e"
failed=0
if bash scripts/run-campaign.sh experiments/rocmfp4-smoke.json rocmfp4-smoke-results > rocmfp4-smoke-results.log 2>&1; then
  bash scripts/run-campaign.sh experiments/rocmfp4-plain.json rocmfp4-plain-results > rocmfp4-plain-results.log 2>&1 || failed=1
else
  printf 'FP4 smoke failed; inspect compatibility before performance ranking\n'
  failed=1
fi
for name in long-context concurrency cpu; do
  status=0
  bash scripts/run-campaign.sh "experiments/$name.json" "$name-results" > "$name-results.log" 2>&1 || status=$?
  printf '%s status=%s\n' "$name" "$status"
  [[ "$status" == 0 ]] || failed=1
done
exit "$failed"
