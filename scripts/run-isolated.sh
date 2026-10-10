#!/usr/bin/env bash
# Serialize a bounded build, correctness check or profiler and restore production.
set -euo pipefail
[[ $# -gt 0 ]] || { echo 'Pass a command and its arguments'; exit 2; }
exec 9>/srv/amd-halo/experiments/benchmark.lock
flock -n 9 || { echo 'Another experiment owns the inference host'; exit 1; }
stack=/srv/amd-halo/stack
script_dir=$(dirname "$(realpath "$0")")
cleanup() {
  status=$?
  trap - EXIT
  bash "$script_dir/restore-service.sh" || exit 1
  exit "$status"
}
trap cleanup EXIT
sudo -n docker compose --project-directory "$stack" -f "$stack/compose.yaml" -f "$stack/compose.mtp.yaml" stop
"$@"
