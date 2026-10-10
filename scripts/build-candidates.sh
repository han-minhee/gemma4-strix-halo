#!/usr/bin/env bash
set -euo pipefail
experiment=${1:?Pass the isolated experiment directory}
shift
names=("$@")
if [[ ${#names[@]} == 0 ]]; then names=(threshold16 rows2 rows8 upstream adaptive rocmfpx lowcols2 lowcols4); fi
export PATH=/srv/amd-halo/rocm-venv/bin:$PATH
export HIP_PATH
HIP_PATH=$(rocm-sdk path --root)
export ROCM_PATH="$HIP_PATH"
export HIPCXX="$HIP_PATH/llvm/bin/clang++"
mkdir -p "$experiment/build-logs"
failed=0
for name in "${names[@]}"; do
  for backend in vulkan hip; do
    if [[ "$backend" == vulkan && "$name" == hip-wide-fa ]]; then continue; fi
    if [[ "$backend" == hip && ( "$name" == threshold16 || "$name" == rows* || "$name" == lowcols* ) ]]; then continue; fi
    source_dir="$experiment/sources/$name"
    build_dir="$experiment/build-$name-$backend"
    opts=(-DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_WEBUI=OFF -DLLAMA_USE_PREBUILT_WEBUI=OFF)
    if [[ "$backend" == vulkan ]]; then opts+=(-DGGML_VULKAN=ON); else
      opts+=(-DGGML_HIP=ON -DGPU_TARGETS=gfx1151 -DCMAKE_HIP_ARCHITECTURES=gfx1151 "-DCMAKE_PREFIX_PATH=$HIP_PATH")
    fi
    if { cmake -S "$source_dir" -B "$build_dir" -G Ninja "${opts[@]}" && cmake --build "$build_dir" -j 8 --target llama-server llama-bench llama-perplexity llama-quantize test-backend-ops; } > "$experiment/build-logs/$name-$backend.log" 2>&1; then
      printf '%s %s OK\n' "$name" "$backend"
      sha256sum "$build_dir/bin/llama-server" > "$experiment/build-logs/$name-$backend.sha256"
    else
      printf '%s %s FAILED\n' "$name" "$backend"
      failed=1
    fi
  done
done
exit "$failed"
