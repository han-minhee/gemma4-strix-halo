#!/usr/bin/env bash
# Restore the production container and wait for application readiness.
set -euo pipefail
stack=/srv/amd-halo/stack
compose=(sudo -n docker compose --project-directory "$stack" -f "$stack/compose.yaml" -f "$stack/compose.mtp.yaml")
"${compose[@]}" start >/dev/null
address=$("${compose[@]}" port inference 8080)
[[ "$address" =~ ^127\.0\.0\.1:[0-9]+$ ]] || { echo 'Unexpected production listen address'; exit 1; }
deadline=$((SECONDS + 300))
until curl --fail --silent --max-time 5 "http://$address/health" >/dev/null; do
  (( SECONDS < deadline )) || { echo 'Production did not become healthy within 300 seconds'; exit 1; }
  sleep 1
done
echo 'Production health: ok'
