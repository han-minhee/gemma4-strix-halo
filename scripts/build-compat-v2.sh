#!/usr/bin/env bash
# Build the second Gemma compatibility candidate without changing the failed one.
set -euo pipefail
experiment=${1:?Pass the experiment directory}
python3 "$experiment/scripts/prepare-kernels.py" "$experiment" rocmfpx-gemma-v2
bash "$experiment/scripts/build-candidates.sh" "$experiment" rocmfpx-gemma-v2
bash "$experiment/scripts/test-candidates.sh" "$experiment" all "$experiment/correctness-compat-v2" rocmfpx-gemma-v2
python3 "$experiment/scripts/collect-builds.py" "$experiment"
