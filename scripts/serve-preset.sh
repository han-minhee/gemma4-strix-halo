#!/usr/bin/env bash
# Preset files contain Compose interpolation values, never shell code or secrets.
set -euo pipefail
preset=${1:-interactive}
[[ $# == 0 ]] || shift
case "$preset" in interactive|long-context|throughput) ;; *)
  echo 'Choose interactive, long-context, or throughput'; exit 2 ;;
esac
stack=$(dirname "$(dirname "$(realpath "$0")")")
operator=${HALO_OPERATOR_ENV:-$stack/.env}
settings="$stack/presets/$preset.env"
[[ -f "$operator" && -f "$settings" ]] || { echo 'Operator configuration or validated preset is missing'; exit 1; }
mtp=$(sed -n 's/^ENABLE_MTP=//p' "$settings")
case "$mtp" in 0|1) ;; *) echo 'Preset must explicitly select ENABLE_MTP=0 or 1'; exit 1 ;; esac
backend=$(sed -n 's/^BACKEND=//p' "$settings")
case "$backend" in vulkan|hip) ;; *) echo 'Preset must explicitly select BACKEND=vulkan or hip'; exit 1 ;; esac
files=(-f "$stack/compose.yaml")
[[ "$backend" != hip ]] || files+=(-f "$stack/compose.hip.yaml")
[[ "$mtp" != 1 ]] || files+=(-f "$stack/compose.mtp.yaml")
[[ $# != 0 ]] || set -- up -d
exec sudo -n docker compose --project-directory "$stack" \
  --env-file "$operator" --env-file "$settings" "${files[@]}" "$@"
