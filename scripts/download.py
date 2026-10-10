#!/usr/bin/env python3
"""Resume pinned model downloads and verify their published SHA256."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("quants", nargs="+", choices=list(json.loads((root / "versions.json").read_text())["files"]))
parser.add_argument("--directory", type=Path, default=root / "models")
parser.add_argument("--transport", choices=["auto", "xet", "curl", "parallel"], default="auto")
parser.add_argument("--connections", type=int, default=32)
args = parser.parse_args()
versions = json.loads((root / "versions.json").read_text())
args.directory.mkdir(parents=True, exist_ok=True)


def parallel_download(url, entry, partial, connections):
    # Separate range files make interruption/resume independent of sparse-file lengths.
    chunks = partial.with_suffix(".chunks")
    chunks.mkdir(exist_ok=True)
    chunk_size = 64 * 1024**2
    spans = [(start, min(start + chunk_size, entry["size"]) - 1)
             for start in range(0, entry["size"], chunk_size)]
    started = time.monotonic()
    completed = 0

    def fetch(span):
        start, end = span
        path = chunks / str(start)
        expected = end - start + 1
        if path.exists() and path.stat().st_size == expected:
            return expected
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=90) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{entry['size']}":
                        raise ValueError("Server did not honor the exact requested range")
                    temp = path.with_suffix(".part")
                    with temp.open("wb") as handle:
                        shutil.copyfileobj(response, handle, 1024**2)
                if temp.stat().st_size != expected:
                    raise ValueError("Incomplete range transfer")
                os.replace(temp, path)
                return expected
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("Unreachable")

    with ThreadPoolExecutor(max_workers=connections) as pool:
        for future in as_completed([pool.submit(fetch, span) for span in spans]):
            completed += future.result()
            seconds = max(time.monotonic() - started, 0.01)
            print(f"{Path(entry['path']).name}: {completed/entry['size']:.1%}, "
                  f"{completed/1024**2/seconds:.1f} MiB/s average", flush=True)
    with partial.open("wb") as output:
        for start, _ in spans:
            with (chunks / str(start)).open("rb") as handle:
                shutil.copyfileobj(handle, output, 8 * 1024**2)


for quant in args.quants:
    entry = versions["files"][quant]
    target = args.directory / Path(entry["path"]).name
    partial = target.with_suffix(".gguf.part")
    if not target.exists():
        remaining = entry["size"] - (partial.stat().st_size if partial.exists() else 0)
        if shutil.disk_usage(args.directory).free < remaining + 2 * 1024**3:
            raise SystemExit("Insufficient disk space for " + quant)
        url = f'https://huggingface.co/{versions["model_repo"]}/resolve/{versions["model_revision"]}/{entry["path"]}'
        if args.transport == "parallel":
            if shutil.disk_usage(args.directory).free < 2 * entry["size"] + 2 * 1024**3:
                raise SystemExit("Insufficient space for range assembly")
            parallel_download(url, entry, partial, max(1, min(args.connections, 64)))
        elif args.transport == "xet":
            os.environ.setdefault("HF_HOME", str(args.directory.parent / "hf-cache"))
            os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
            from huggingface_hub import hf_hub_download
            source = Path(hf_hub_download(repo_id=versions["model_repo"], filename=entry["path"],
                                         revision=versions["model_revision"], local_dir=args.directory / "hf"))
        elif args.transport == "auto" and shutil.which("aria2c"):
            subprocess.run(["aria2c", "--continue=true", "--auto-file-renaming=false", "--allow-overwrite=true",
                            "--max-connection-per-server=16", "--split=16", "--min-split-size=64M",
                            "--summary-interval=30", "--console-log-level=warn", "--file-allocation=none",
                            "--show-console-readout=false",
                            "--dir=" + str(partial.parent), "--out=" + partial.name, url], check=True)
        else:
            subprocess.run(["curl", "--fail", "--location", "--retry", "5", "--continue-at", "-",
                            "--output", str(partial), url], check=True)
        if args.transport != "xet":
            source = partial
    else:
        source = target
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    if source.stat().st_size != entry["size"] or digest.hexdigest() != entry["sha256"]:
        raise SystemExit(f"Checksum/size mismatch: {source}; preserved for diagnosis")
    if source != target:
        os.replace(source, target)
    print(f"Verified {quant}: {target}", flush=True)
