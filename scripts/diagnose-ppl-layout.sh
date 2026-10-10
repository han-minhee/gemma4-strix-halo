#!/usr/bin/env bash
set -euo pipefail
e=${1:?experiment directory}
out="$e/ppl-layout-diagnostic"
mkdir "$out"
source=/srv/amd-halo/stack/.runtime/llama.cpp
bin=/srv/amd-halo/stack/.runtime/build-vulkan/bin
g++ -O2 -std=c++17 "$e/experiments/logit-probe.cpp" -I"$source/include" -I"$source/ggml/include" \
  -L"$bin" -Wl,-rpath,"$bin" -lllama -lggml -lggml-base -o "$e/logit-probe"
sha256sum "$e/logit-probe" "$e/experiments/logit-probe.cpp" > "$out/probe.sha256"
for variant in current-stride old-vulkan; do
  binary=/srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-perplexity
  extra=(--ppl-stride 256)
  if [[ "$variant" == old-vulkan ]]; then
    binary="$e/build-rocmfpx-vulkan/bin/llama-perplexity"
    extra=()
  fi
  command=("$binary" -m /srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf -f "$e/quality-data/wikipedia-en.txt" -c 512 -b 512 -ub 512 -ngl 999 -fa on -t 2 --fit off --chunks 2 "${extra[@]}")
  printf '%q ' "${command[@]}" > "$out/$variant.command"
  "${command[@]}" > "$out/$variant.stdout" 2> "$out/$variant.stderr"
done
"$e/logit-probe" /srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf "$e/quality-data/wikipedia-en.txt" > "$out/independent.stdout" 2> "$out/independent.stderr"
