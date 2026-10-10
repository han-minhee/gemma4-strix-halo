#!/usr/bin/env python3
"""Measure uncached HTTP requests, first token latency and model timings."""
import argparse
import json
from pathlib import Path
import time
import urllib.request

PROMPTS = {
    "prose": "Explain unified memory and why a dense language model can be limited by memory bandwidth. Write three detailed paragraphs.",
    "code": "Write a Python implementation of an LRU cache with get and put, O(1) operations, type hints, and a short usage example.",
    "korean": "한국어로 CPU와 GPU의 공유 메모리가 대규모 언어 모델 추론 성능에 어떤 영향을 주는지 세 문단으로 설명해 주세요.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--tokens", type=int, default=128)
    args = parser.parse_args()
    headers = {"Content-Type": "application/json"}
    if args.key_file:
        headers["Authorization"] = "Bearer " + args.key_file.read_text().strip()

    def request(path, payload):
        req = urllib.request.Request(args.url.rstrip("/") + path, json.dumps(payload).encode(), headers)
        return urllib.request.urlopen(req, timeout=600)

    rows = []
    for name, prompt in PROMPTS.items():
        with request("/apply-template", {"messages": [{"role": "user", "content": prompt}],
                                         "chat_template_kwargs": {"enable_thinking": False}}) as response:
            rendered = json.load(response)["prompt"]
        # One unreported warm request per prompt; cache is disabled in measured requests too.
        for repeat in range(-1, args.repetitions):
            payload = {"prompt": rendered, "stream": True, "n_predict": args.tokens,
                       "temperature": 0, "seed": 1234, "cache_prompt": False, "ignore_eos": True}
            started = time.monotonic()
            first = None
            text = ""
            last = {}
            with request("/completion", payload) as response:
                for line in response:
                    if not line.startswith(b"data: "):
                        continue
                    data = line[6:].strip()
                    if data == b"[DONE]":
                        continue
                    event = json.loads(data)
                    if event.get("content"):
                        first = first or time.monotonic()
                        text += event["content"]
                    if event.get("stop"):
                        last = event
            if not last or not text.strip() or first is None:
                raise RuntimeError("Server did not produce a complete, nonempty response")
            row = {"prompt": name, "repeat": repeat, "ttft_seconds": first - started,
                   "elapsed_seconds": time.monotonic() - started, "timings": last.get("timings"),
                   "tokens_predicted": last.get("tokens_predicted"), "text": text}
            if repeat >= 0:
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if k != "text"}), flush=True)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
