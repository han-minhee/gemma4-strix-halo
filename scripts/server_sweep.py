#!/usr/bin/env python3
"""Compare native HTTP serving without leaving benchmark processes running."""
import argparse
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from profile import sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["baseline", "mtp2", "mtp4", "mtp8", "mtp-cpu4"])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--tokens", type=int, default=128)
    parser.add_argument("flags", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    # Unsupported placements can abort in upstream assertions. Retain startup
    # logs and status without generating a model-sized core dump.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    flags = args.flags[1:] if args.flags[:1] == ["--"] else args.flags
    args.output.mkdir(parents=True, exist_ok=True)
    key = args.key_file.read_text().strip()
    for name in args.cases:
        configuration = name.split("@", 1)[0]
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        command = [str(args.binary), "--model", str(args.model), "--host", "127.0.0.1",
                   "--port", str(port), "--api-key-file", str(args.key_file), "--parallel", "1",
                   "--reasoning-budget", "0", *flags]
        if configuration != "baseline":
            count = "4" if configuration == "mtp-cpu4" else configuration.removeprefix("mtp").split("-p")[0]
            command += ["--model-draft", str(args.draft), "--spec-type", "draft-mtp", "--spec-draft-n-max", count]
            if "-p" in configuration:
                command += ["--spec-draft-p-min", configuration.split("-p", 1)[1]]
            if configuration == "mtp-cpu4":
                command += ["--spec-draft-device", "none", "--spec-draft-ngl", "0", "--spec-draft-threads", "16"]
        telemetry = []
        stop = threading.Event()

        def monitor():
            while not stop.is_set():
                telemetry.append(sample())
                stop.wait(1)

        thread = threading.Thread(target=monitor)
        started = time.time()
        status = None
        with (args.output / f"{name}.log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            thread.start()
            try:
                url = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 300
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Server exited with {process.returncode}")
                    try:
                        req = urllib.request.Request(url + "/health", headers={"Authorization": "Bearer " + key})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("Server readiness timed out")
                    time.sleep(1)
                result = subprocess.run(["python3", str(Path(__file__).with_name("http_profile.py")),
                                         "--url", url, "--key-file", str(args.key_file), "--output",
                                         str(args.output / f"{name}.json"), "--repetitions", str(args.repetitions),
                                         "--tokens", str(args.tokens)], check=False)
                status = result.returncode
            except Exception as error:
                status = str(error)
                print(f"{name}: {error}; retained startup log", flush=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                stop.set()
                thread.join()
                (args.output / f"{name}.meta.json").write_text(json.dumps({
                    "command": command, "status": status, "elapsed_seconds": time.time() - started,
                    "environment": {k: v for k, v in os.environ.items() if k.startswith(("GGML_", "RADV_", "MESA_", "HIP_", "HSA_"))},
                    "telemetry": telemetry}, indent=2))


if __name__ == "__main__":
    main()
