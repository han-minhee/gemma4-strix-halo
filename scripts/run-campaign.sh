#!/usr/bin/env bash
# Restore the known production container after a serial native test batch.
set -euo pipefail
manifest=${1:?Pass the manifest}
output=${2:?Pass a new result directory}
script_dir=$(dirname "$(realpath "$0")")
manifest=$(realpath "$manifest")
output=$(realpath -m "$output")
exec 9>/srv/amd-halo/experiments/benchmark.lock
flock -n 9 || { echo 'Another experiment owns the inference host'; exit 1; }
cd /srv/amd-halo/stack
cleanup() {
  status=$?
  trap - EXIT
  bash "$script_dir/restore-service.sh" || exit 1
  exit "$status"
}
trap cleanup EXIT
sudo -n docker compose -f compose.yaml -f compose.mtp.yaml stop
python3 "$script_dir/campaign.py" "$manifest" --output "$output"
