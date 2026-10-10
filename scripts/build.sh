#!/usr/bin/env bash
set -euo pipefail
backend=${1:-vulkan}
if [[ $# -gt 0 ]]; then shift; fi
case "$backend" in vulkan|hip|cpu) ;; *) echo 'Backend must be vulkan, hip, or cpu' >&2; exit 2 ;; esac
repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
runtime=${HALO_RUNTIME:-"$repo_root/.runtime"}
commit=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_commit"])' "$repo_root/versions.json")
release=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_release"])' "$repo_root/versions.json")
mkdir -p "$runtime"
if [[ ! -d "$runtime/llama.cpp/.git" ]]; then
    git clone --depth=1 --branch "$release" https://github.com/ggml-org/llama.cpp.git "$runtime/llama.cpp"
fi
if [[ -n $(git -C "$runtime/llama.cpp" status --porcelain) ]]; then
    echo 'Refusing to overwrite a modified llama.cpp checkout' >&2; exit 1
fi
git -C "$runtime/llama.cpp" fetch origin "$commit"
git -C "$runtime/llama.cpp" checkout --detach "$commit"
opts=(-DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF)
if [[ "$backend" == vulkan ]]; then opts+=(-DGGML_VULKAN=ON); fi
if [[ "$backend" == hip ]]; then
    : "${HIP_PATH:?Set HIP_PATH to the verified ROCm installation}"
    export ROCM_PATH="$HIP_PATH"
    export HIPCXX="$HIP_PATH/llvm/bin/clang++"
    opts+=(-DGGML_HIP=ON -DGPU_TARGETS=gfx1151 "-DCMAKE_PREFIX_PATH=$HIP_PATH")
fi
cmake -S "$runtime/llama.cpp" -B "$runtime/build-$backend" -G Ninja "${opts[@]}" "$@" || {
    # The backend argument is consumed above; additional CMake flags are optional.
    echo 'CMake configuration failed; check installed headers/toolchain' >&2; exit 1
}
cmake --build "$runtime/build-$backend" --parallel "${BUILD_JOBS:-8}" --target llama-server llama-bench llama-cli llama-perplexity llama-quantize
"$runtime/build-$backend/bin/llama-server" --version
"$runtime/build-$backend/bin/llama-bench" --list-devices
