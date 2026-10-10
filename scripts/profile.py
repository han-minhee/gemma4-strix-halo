#!/usr/bin/env python3
"""Serial llama-bench comparisons with host telemetry and full commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time


def sample():
    values = {"time": time.time(), "load": os.getloadavg()}
    paths = [Path("/proc/meminfo"), Path("/proc/stat"), Path("/proc/pressure/memory"),
             Path("/sys/firmware/acpi/platform_profile"),
             Path("/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"),
             Path("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference")]
    paths += list(Path("/sys/class/drm").glob("card[0-9]/device/gpu_busy_percent"))
    paths += list(Path("/sys/class/drm").glob("card[0-9]/device/mem_info_*_used"))
    paths += list(Path("/sys/class/drm").glob("card[0-9]/device/pp_dpm_*clk"))
    paths += list(Path("/sys/class/hwmon").glob("hwmon*/temp*_input"))
    paths += list(Path("/sys/class/hwmon").glob("hwmon*/temp*_label"))
    paths += list(Path("/sys/class/hwmon").glob("hwmon*/name"))
    paths += list(Path("/sys/class/hwmon").glob("hwmon*/power*_average"))
    paths += list(Path("/sys/class/hwmon").glob("hwmon*/freq*_input"))
    for field in ("name", "energy_uj", "max_energy_range_uj"):
        paths += list(Path("/sys/class/powercap").glob("intel-rapl*/" + field))
    for path in paths:
        try:
            values[str(path)] = path.read_text().strip()
        except OSError:
            pass
    return values


def run_case(binary, model, output, label, flags, repetitions, prompt, generate, depth, env_overrides=None):
    command = [str(binary), "-m", str(model), "-p", str(prompt), "-n", str(generate),
               "-d", str(depth), "-r", str(repetitions), "-o", "json", *flags]
    print(label, flush=True)
    stop = threading.Event()
    telemetry = []

    def monitor():
        while not stop.is_set():
            telemetry.append(sample())
            stop.wait(1)

    thread = threading.Thread(target=monitor)
    thread.start()
    started = time.time()
    status = None
    try:
        with (output / f"{label}.json").open("w") as stdout, (output / f"{label}.log").open("w") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=1800, check=False,
                                    env=os.environ | (env_overrides or {}))
            status = result.returncode
    except subprocess.TimeoutExpired:
        status = "timeout"
    finally:
        stop.set()
        thread.join()
        (output / f"{label}.meta.json").write_text(json.dumps({
            "command": command, "returncode": status, "elapsed_seconds": time.time() - started,
            "environment_overrides": env_overrides or {},
            "telemetry": telemetry}, indent=2))
    if status != 0:
        print(f"{label} failed: see {output / (label + '.log')}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, default=Path(__file__).resolve().parents[1] / ".runtime")
    parser.add_argument("--backends", nargs="+", default=["vulkan", "hip"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--prompt", type=int, default=512)
    parser.add_argument("--generate", type=int, default=128)
    parser.add_argument("--depth", type=int, default=0)
    parser.add_argument("--cases", nargs="+", help="Run only these named cases")
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error("Model does not exist")
    args.output.mkdir(parents=True, exist_ok=True)
    for backend in args.backends:
        binary = args.runtime / f"build-{backend}/bin/llama-bench"
        if not binary.is_file():
            print(f"Skip {backend}: executable absent", flush=True)
            continue
        cases = {
            "full-t2": ["-ngl", "999", "-t", "2", "-fa", "on", "-lm", "none"],
            "full-t8": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none"],
            "full-t16": ["-ngl", "999", "-t", "16", "-fa", "on", "-lm", "none"],
            "full-no-fa": ["-ngl", "999", "-t", "8", "-fa", "off", "-lm", "none"],
            "full-mmap": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "mmap"],
            "full-ub256": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none", "-ub", "256"],
            "full-ub1024": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none", "-ub", "1024"],
            "full-q8kv": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none", "-ctk", "q8_0", "-ctv", "q8_0"],
            "full-poll0": ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none", "--poll", "0"],
            "hybrid-40": ["-ngl", "40", "-t", "16", "-fa", "on", "-lm", "none"],
        }
        if backend == args.backends[0]:
            cases["cpu-t16"] = ["-ngl", "0", "-t", "16", "-fa", "off", "-lm", "mmap"]
            cases["cpu-t32"] = ["-ngl", "0", "-t", "32", "-fa", "off", "-lm", "mmap"]
        if backend == "hip":
            cases["full-unified"] = ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none"]
            cases["full-graph-opt"] = ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none"]
        if backend == "vulkan":
            cases["full-graphics-queue"] = ["-ngl", "999", "-t", "8", "-fa", "on", "-lm", "none"]
        environments = {"full-unified": {"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"},
                        "full-graph-opt": {"GGML_CUDA_GRAPH_OPT": "1"},
                        "full-graphics-queue": {"GGML_VK_ALLOW_GRAPHICS_QUEUE": "1"}}
        for name, flags in cases.items():
            if args.cases and name not in args.cases:
                continue
            run_case(binary, args.model, args.output, f"{backend}-{name}", flags,
                     args.repetitions, args.prompt, args.generate, args.depth,
                     environments.get(name))
    summary = []
    for path in sorted(args.output.glob("*.json")):
        if path.name.endswith(".meta.json") or path.name == "summary.json":
            continue
        try:
            for row in json.loads(path.read_text()):
                summary.append({"case": path.stem, "prompt": row["n_prompt"], "generate": row["n_gen"],
                                "tokens_per_second": row["avg_ts"], "stddev": row["stddev_ts"]})
        except (ValueError, KeyError, TypeError):
            continue
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    for row in summary:
        print(f'{row["case"]}: pp{row["prompt"]}/tg{row["generate"]} '
              f'{row["tokens_per_second"]:.2f} +/- {row["stddev"]:.2f} t/s')


if __name__ == "__main__":
    main()
