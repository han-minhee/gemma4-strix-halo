#!/usr/bin/env bash
# Start only after build-second-batch.sh and its numerical checks pass.
set -euo pipefail
experiment=${1:?Pass the experiment directory}
runner="$experiment/scripts/run-campaign.sh"
# A failed harness smoke blocks all measurements made with that harness.
bash "$runner" "$experiment/experiments/thermal-smoke.json" "$experiment/thermal-smoke-results" \
  > "$experiment/thermal-smoke-results.log" 2>&1
failed=0
for name in low-columns draft-precision target-quants rocmfpx-repair-smoke rocmfpx-repair; do
  status=0
  bash "$runner" "$experiment/experiments/$name.json" "$experiment/$name-results" \
    > "$experiment/$name-results.log" 2>&1 || status=$?
  printf '%s\n' "$status" > "$experiment/$name-results.status"
  printf '%s status=%s\n' "$name" "$status"
  [[ "$status" == 0 ]] || failed=1
done
exit "$failed"
