#!/usr/bin/env bash
set -euo pipefail
e=${1:?experiment directory}
for quant in Q4_K_M Q4_0 Q4_K_M-Q8KV; do
  source="$e/quality-coding-q4-results/$quant"
  mkdir -p "$e/quality/$quant"
  for mapping in result.json:canaries.json humaneval.json:humaneval.json; do
    input=${mapping%%:*}; output=${mapping#*:}
    [[ ! -e "$e/quality/$quant/$output" ]] || { echo 'Refuse to overwrite assembled quality evidence'; exit 1; }
    [[ ! -f "$source/$input" ]] || cp "$source/$input" "$e/quality/$quant/$output"
  done
done
# Gates may reject a candidate; retain that result without stopping other tests.
python3 "$e/scripts/quality-gate.py" --baseline "$e/quality/Q4_K_M" --candidate "$e/quality/Q4_0" >"$e/quality/Q4_0/gate.json" || true
python3 "$e/scripts/quality-gate.py" --baseline "$e/quality/Q4_K_M" --candidate "$e/quality/Q4_K_M-Q8KV" --allow-kv-change >"$e/quality/Q4_K_M-Q8KV/gate.json" || true
