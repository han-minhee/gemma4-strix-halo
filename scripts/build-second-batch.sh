#!/usr/bin/env bash
# Invoke through run-isolated.sh after the original runtime screen finishes.
set -euo pipefail
experiment=${1:?Pass the experiment directory}
python3 "$experiment/scripts/prepare-kernels.py" "$experiment" lowcols2 lowcols4 rocmfpx-gemma
bash "$experiment/scripts/build-candidates.sh" "$experiment" lowcols2 lowcols4 rocmfpx-gemma
bash "$experiment/scripts/test-candidates.sh" "$experiment" all "$experiment/correctness-second" lowcols2 lowcols4 rocmfpx-gemma
python3 "$experiment/scripts/collect-builds.py" "$experiment"
