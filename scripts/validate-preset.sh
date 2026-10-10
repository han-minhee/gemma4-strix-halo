#!/usr/bin/env bash
# Deploy one qualified preset, test it, and restore the preserved stack on failure.
# Keep /srv/amd-halo/stack unchanged; stage this checkout in a separate directory.
set -euo pipefail
preset=${1:?preset name}
output=$(realpath -m "${2:?new output directory}")
stack=$(dirname "$(dirname "$(realpath "$0")")")
original=/srv/amd-halo/stack
[[ "$stack" != "$original" ]] || { echo 'Validation requires a separate staged stack'; exit 1; }
[[ ! -e "$output" ]] || { echo 'Refuse to overwrite validation evidence'; exit 1; }
exec 9>/srv/amd-halo/experiments/benchmark.lock
flock -n 9 || { echo 'Another experiment owns the inference host'; exit 1; }
mkdir -p "$output"
started=$(date +%s)
cleanup() {
  status=$?
  trap - EXIT
  if [[ "$status" != 0 ]]; then
    sudo -n docker compose --project-directory "$original" -f "$original/compose.yaml" -f "$original/compose.mtp.yaml" up -d
    bash "$stack/scripts/restore-service.sh"
  fi
  exit "$status"
}
trap cleanup EXIT
health() {
  local deadline=$((SECONDS + 300))
  until curl --fail --silent --max-time 5 http://127.0.0.1:8080/health >/dev/null; do
    (( SECONDS < deadline )) || return 1
    sleep 1
  done
}
bash "$stack/scripts/serve-preset.sh" "$preset" up -d
health
python3 - "$stack/presets/$preset.env" >"$output/effective-settings.json" <<'PY'
import json,sys,urllib.request
from pathlib import Path
settings=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if line and not line.startswith('#'))
key=Path('/srv/amd-halo/secrets/api-key').read_text().strip()
request=urllib.request.Request('http://127.0.0.1:8080/props',headers={'Authorization':'Bearer '+key})
with urllib.request.urlopen(request,timeout=15) as response: props=json.load(response)
assert props['total_slots']==int(settings['PARALLEL'])
assert props['default_generation_settings']['n_ctx']==int(settings['CONTEXT'])//int(settings['PARALLEL'])
assert Path(props['model_path']).name==Path(settings['MODEL_FILE']).name
print(json.dumps(props,indent=2))
PY
sudo -n docker inspect --format '{{.Image}}' amd-halo-gemma4-inference-1 >"$output/image-id"
expected_image=$(sed -n 's/^HALO_IMAGE=//p' "$stack/presets/$preset.env")
[[ "$expected_image" == sha256:* && "$(cat "$output/image-id")" == "$expected_image" ]] || { echo 'Deployed image differs from qualified preset'; exit 1; }
sudo -n docker inspect --format '{{json .Config.Cmd}}' amd-halo-gemma4-inference-1 >"$output/command.json"
cp "$stack/presets/$preset.env" "$output/preset.env"
python3 "$stack/scripts/validate_service.py" --key-file /srv/amd-halo/secrets/api-key --output "$output/canaries-before.json"
clients=$(sed -n 's/^PARALLEL=//p' "$stack/presets/$preset.env")
python3 "$stack/scripts/soak-service.py" --key-file /srv/amd-halo/secrets/api-key --output "$output/soak" --seconds 600 --clients "$clients"
bash "$stack/scripts/serve-preset.sh" "$preset" restart inference
health
python3 "$stack/scripts/validate_service.py" --key-file /srv/amd-halo/secrets/api-key --output "$output/canaries-after-restart.json"
sudo -n journalctl -k --since "@$started" --no-pager >"$output/kernel.log"
if grep -Eiq 'amdgpu.*(GPU reset|ring.*timeout|VM.*fault)|Out of memory: Killed process|oom-kill:' "$output/kernel.log"; then
  echo 'Kernel fault detected during validation'; exit 1
fi
printf '{"status":"ok","preset":"%s","started":%s,"finished":%s}\n' "$preset" "$started" "$(date +%s)" >"$output/validation.json"
printf 'Preset %s passed deployment, sustained load and restart checks\n'  "$preset"
