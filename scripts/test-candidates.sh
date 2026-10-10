#!/usr/bin/env bash
# Run under the experiment lock, with the production service stopped.
set -euo pipefail
experiment=${1:?Pass the isolated experiment directory}
mode=${2:-all}
output=${3:-$experiment/correctness}
mkdir -p "$output"
failed=0
names=(baseline threshold16 rows2 rows8 upstream adaptive rocmfpx lowcols2 lowcols4)
if [[ $# -gt 3 ]]; then names=("${@:4}"); fi
types='q4_K|q6_K|q8_0|q4_0|iq4_xs|q4_0_rocmfp4|q4_0_rocmfp4_fast|f16'
[[ "$mode" != k-only ]] || types='q4_K|q6_K'
for name in "${names[@]}"; do
  for backend in vulkan hip; do
    binary="$experiment/build-$name-$backend/bin/test-backend-ops"
    if [[ "$name" == baseline ]]; then binary="/srv/amd-halo/stack/.runtime/build-$backend/bin/test-backend-ops"; fi
    [[ -x "$binary" ]] || continue
    device=Vulkan0
    [[ "$backend" != hip ]] || device=ROCm0
    status=0
    if [[ "$mode" != fa-only ]]; then
    timeout 1200 "$binary" test -b "$device" -o MUL_MAT \
      -p "type_a=($types),.*n=(1|2|3|4|5|6|7|8|9|12|13|16|17)," \
      > "$output/$name-$backend.log" 2>&1 || status=$?
    grep -Eq '[1-9][0-9]*/[1-9][0-9]* tests passed' "$output/$name-$backend.log" || status=66
    for type in q4_K q6_K; do
      grep -Eq "MUL_MAT\(type_a=$type,.*OK" "$output/$name-$backend.log" || status=67
    done
    printf '%s\n' "$status" > "$output/$name-$backend.status"
    printf '%s %s status=%s\n' "$name" "$backend" "$status"
    [[ "$status" == 0 ]] || failed=1
    fi
    [[ "$mode" != k-only ]] || continue
    status=0
    timeout 600 "$binary" test -b "$device" -o FLASH_ATTN_EXT \
      -p 'hsk=(64|256|512),.*kv=(512|1024),nb=(1|32),mask=1,sinks=0,max_bias=0[.0]*,logit_softcap=0[.0]*,.*type_K=(f16|q8_0|q4_0),' \
      > "$output/$name-$backend-fa.log" 2>&1 || status=$?
    grep -Eq '[1-9][0-9]*/[1-9][0-9]* tests passed' "$output/$name-$backend-fa.log" || status=66
    printf '%s\n' "$status" > "$output/$name-$backend-fa.status"
    printf '%s %s flash-attention status=%s\n' "$name" "$backend" "$status"
    [[ "$status" == 0 ]] || failed=1
  done
done
exit "$failed"
