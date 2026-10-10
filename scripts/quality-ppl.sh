#!/usr/bin/env bash
set -euo pipefail
binary=${1:?llama-perplexity binary}
model=${2:?model}
corpus=${3:?directory containing wikipedia-en.txt and wikipedia-ko.txt}
output=${4:?new output directory}
kv=${5:-f16}
[[ -x "$binary" ]] || { echo 'Perplexity executable is missing; build the pinned llama-perplexity target first'; exit 1; }
case "$kv" in f16|q8_0|q4_0) ;; *) echo 'Unsupported quality-screen KV format'; exit 2 ;; esac
[[ ! -e "$output" ]] || { echo 'Choose a new perplexity output directory'; exit 1; }
mkdir -p "$output"
script_dir=$(dirname "$(realpath "$0")")
python3 - "$corpus" "$script_dir/../experiments/quality-data.json" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for entry in json.loads(Path(sys.argv[2]).read_text())['files']:
    path=root/entry['file']
    with path.open('rb') as handle: digest=hashlib.file_digest(handle,'sha256').hexdigest()
    if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
        raise SystemExit('Quality-data integrity failure: '+str(path))
PY
sha256sum "$binary" "$model" "$corpus/wikipedia-en.txt" "$corpus/wikipedia-ko.txt" > "$output/inputs.sha256"
for language in en ko; do
 command=("$binary" -m "$model" -f "$corpus/wikipedia-$language.txt" -c 512 -b 512 -ub 512
          -ngl 999 -fa on -t 2 --fit off --chunks 32 --cache-type-k "$kv" --cache-type-v "$kv")
 printf '%q ' "${command[@]}" > "$output/$language.command"
 printf '\n' >> "$output/$language.command"
 "${command[@]}" > "$output/$language.stdout" 2> "$output/$language.stderr"
done
