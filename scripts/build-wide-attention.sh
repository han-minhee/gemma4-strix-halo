#!/usr/bin/env bash
# Invoke through run-isolated.sh; never compile during measured inference.
set -euo pipefail
e=${1:?experiment directory}
python3 "$e/scripts/prepare-kernels.py" "$e" hip-wide-fa
bash "$e/scripts/build-candidates.sh" "$e" hip-wide-fa
bash "$e/scripts/test-candidates.sh" "$e" fa-only "$e/correctness-wide-fa" hip-wide-fa
binary="$e/build-hip-wide-fa-hip/bin/test-backend-ops"
log="$e/correctness-wide-fa/wide-boundary.log"
timeout 1200 "$binary" test -b ROCm0 -o FLASH_ATTN_EXT \
  -p 'hsk=512,hsv=512,nh=4,nr23=\[(4|8),1\],kv=(1024|16384|32768),nb=(16|17|32|33|64|128|129|256|512|1024),mask=1,sinks=0,max_bias=0[.0]*,logit_softcap=0[.0]*,.*type_K=(f16|q8_0|q4_0),' > "$log" 2>&1
grep -Eq '62/62 tests passed' "$log"
for gqa in 4 8; do
  for width in 16 17 32 33 64 128 129 256 512 1024; do
    for type in f16 q8_0 q4_0; do
      grep -Eq "nr23=\\[$gqa,1\\],kv=1024,nb=$width,.*type_K=$type,.*OK" "$log"
    done
  done
done
for length in 16384 32768; do
  grep -Eq "kv=$length,nb=512,.*type_K=f16,.*OK" "$log"
done
python3 "$e/scripts/collect-builds.py" "$e"
