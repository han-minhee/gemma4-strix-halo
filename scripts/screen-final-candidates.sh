#!/usr/bin/env bash
# Run after the serving screen, with current scripts copied before this starts.
# Each operation owns the host lock and restores healthy production on exit.
set -euo pipefail
e=${1:?experiment directory}
cd "$e"
status=0
bash scripts/run-campaign.sh experiments/thermal-smoke-v3.json thermal-smoke-v3-results >thermal-smoke-v3-results.log 2>&1 || status=1
python3 scripts/validate_service.py --key-file /srv/amd-halo/secrets/api-key --output baseline-service-validation-v3.json >baseline-service-validation-v3.log 2>&1 || status=1
if bash scripts/run-isolated.sh bash scripts/build-wide-attention.sh "$e" >build-wide-attention.log 2>&1; then
  if bash scripts/run-campaign.sh experiments/hip-wide-smoke.json hip-wide-smoke-results >hip-wide-smoke-results.log 2>&1 && python3 -c 'import json; d=json.load(open("hip-wide-smoke-results/hip-wide-smoke/result.json")); assert d["status"]=="ok" and all(r.get("correct") is not False for b in d["rows"] for r in b["requests"])'; then
    bash scripts/run-campaign.sh experiments/hip-wide-fa.json hip-wide-fa-results >hip-wide-fa-results.log 2>&1 || status=1
  else
    status=1
  fi
else
  printf 'Wide attention build/correctness rejected; inspect retained log\n'
  status=1
fi
bash scripts/run-isolated.sh bash scripts/quality-ppl.sh /srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-perplexity /srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf "$e/quality-data" "$e/quality/Q4_K_M-Q8KV/ppl" q8_0 >quality-q8-kv-ppl.log 2>&1 || status=1
bash scripts/run-campaign.sh experiments/quality-coding-q4.json quality-coding-q4-results >quality-coding-q4-results.log 2>&1 || status=1
bash scripts/assemble-quality.sh "$e" >assemble-quality.log 2>&1 || status=1
if python3 -c 'import json; assert json.load(open("quality/Q4_0/gate.json"))["passed"]'; then
  bash scripts/run-campaign.sh experiments/q4-depth-refinement.json q4-depth-refinement-results >q4-depth-refinement-results.log 2>&1 || status=1
fi
bash scripts/run-campaign.sh experiments/sampling.json sampling-results >sampling-results.log 2>&1 || status=1
bash scripts/run-campaign.sh experiments/long-microbatch.json long-microbatch-results >long-microbatch-results.log 2>&1 || status=1
bash scripts/run-campaign.sh experiments/concurrency-kernels.json concurrency-kernels-results >concurrency-kernels-results.log 2>&1 || status=1
bash scripts/run-campaign.sh experiments/hip-capacity.json hip-capacity-results >hip-capacity-results.log 2>&1 || status=1
bash scripts/run-isolated.sh bash scripts/screen-epp.sh "$e" >screen-epp.log 2>&1 || status=1
exit "$status"
