#!/usr/bin/env bash
# Run under run-isolated.sh so CPU policy testing cannot overlap inference.
set -euo pipefail
e=${1:?experiment directory}
python3 "$e/scripts/campaign.py" "$e/experiments/epp.json" --output "$e/epp-before-results"
python3 "$e/scripts/epp-campaign.py" "$e/experiments/epp.json" --output "$e/epp-performance-results"
python3 "$e/scripts/campaign.py" "$e/experiments/epp.json" --output "$e/epp-after-results"
