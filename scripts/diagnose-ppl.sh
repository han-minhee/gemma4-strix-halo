#!/usr/bin/env bash
# Small cross-runtime and microbatch checks before trusting the quality gate.
set -euo pipefail
e=${1:?experiment directory}
out="$e/ppl-diagnostic"
mkdir "$out"
model=/srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf
for variant in baseline-split baseline-smallub baseline-no-fa upstream-vulkan upstream-hip baseline-cpu; do
  binary=/srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-perplexity
  batch=512; ubatch=512; fa=on; gpu=999; threads=2
  case "$variant" in
    baseline-split) batch=256; ubatch=256 ;;
    baseline-smallub) ubatch=8 ;;
    baseline-no-fa) fa=off ;;
    baseline-cpu) gpu=0; threads=16 ;;
    upstream-*) binary="$e/build-$variant/bin/llama-perplexity" ;;
  esac
  command=("$binary" -m "$model" -f "$e/quality-data/wikipedia-en.txt" -c 512 -b "$batch" -ub "$ubatch" -ngl "$gpu" -fa "$fa" -t "$threads" --fit off --chunks 2)
  printf '%q ' "${command[@]}" > "$out/$variant.command"
  "${command[@]}" > "$out/$variant.stdout" 2> "$out/$variant.stderr" || printf '%s failed\n' "$variant"
done
