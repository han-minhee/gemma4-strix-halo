#!/usr/bin/env bash
# Run via run-isolated.sh; retain every arm even if another arm fails.
set -euo pipefail
experiment=${1:?Pass the experiment directory}
binary=/srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-perplexity
failed=0
for quant in Q4_K_M IQ4_XS Q4_0; do
  output="$experiment/quality/$quant/ppl"
  mkdir -p "$(dirname "$output")"
  status=0
  bash "$experiment/scripts/quality-ppl.sh" "$binary" \
    "/srv/amd-halo/models/gemma-4-31B-it-$quant.gguf" "$experiment/quality-data" "$output" || status=$?
  printf '%s\n' "$status" > "$experiment/quality/$quant/ppl.status"
  printf '%s perplexity status=%s\n' "$quant" "$status"
  [[ "$status" == 0 ]] || failed=1
done
exit "$failed"
