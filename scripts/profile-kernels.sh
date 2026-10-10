#!/usr/bin/env bash
set -euo pipefail
experiment=${1:?Pass the isolated experiment directory}
mkdir -p "$experiment/kernel-profile"
cd /srv/amd-halo/stack
exec 9>/srv/amd-halo/experiments/benchmark.lock
flock -n 9 || exit 1
trap 'sudo -n docker compose -f compose.yaml -f compose.mtp.yaml start >/dev/null' EXIT
sudo -n docker compose -f compose.yaml -f compose.mtp.yaml stop
set +e
PATH=/srv/amd-halo/rocm-venv/bin:$PATH GGML_CUDA_GRAPH_OPT=1 \
 /srv/amd-halo/rocm-venv/bin/rocprofv3 --kernel-trace --hip-trace --stats --output-format csv \
 --output-directory "$experiment/kernel-profile/hip" -- \
 .runtime/build-hip/bin/llama-bench -m /srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf \
 -ngl 999 -t 2 -fa on -lm none -p 512 -n 16 -r 1 -o json \
 > "$experiment/kernel-profile/hip.stdout" 2> "$experiment/kernel-profile/hip.stderr"
echo "$?" > "$experiment/kernel-profile/hip.status"
for depth in 4 8; do
 GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_LOGGER_FREQUENCY=100 \
 python3 "$experiment/scripts/server_sweep.py" --binary /srv/amd-halo/stack/.runtime/build-vulkan/bin/llama-server \
 --model /srv/amd-halo/models/gemma-4-31B-it-Q4_K_M.gguf \
 --draft /srv/amd-halo/models/mtp-gemma-4-31B-it-Q8_0.gguf \
 --key-file /srv/amd-halo/secrets/api-key --output "$experiment/kernel-profile/vulkan-$depth" \
 --cases "mtp$depth" --repetitions 1 --tokens 32 -- \
 --n-gpu-layers 999 --threads 2 --threads-batch 2 --ctx-size 8192 \
 --batch-size 2048 --ubatch-size 512 --flash-attn on --cache-type-k f16 --cache-type-v f16 --load-mode none --verbosity 4 \
 > "$experiment/kernel-profile/vulkan-$depth.stdout" 2>&1
 echo "$?" > "$experiment/kernel-profile/vulkan-$depth.status"
done
