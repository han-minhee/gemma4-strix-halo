#!/usr/bin/env python3
"""Exercise authenticated serving, ordinary EOS, Korean, Python and long context."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.url.rstrip("/")
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + args.key_file.read_text().strip()}

    def request(path, payload=None, authenticated=True):
        req = urllib.request.Request(base + path,
                                     None if payload is None else json.dumps(payload).encode(),
                                     headers if authenticated else {})
        with urllib.request.urlopen(req, timeout=600) as response:
            return json.load(response)

    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.meta.json').write_text(json.dumps({
        'started': time.time(), 'url': base,
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'effective_settings': request('/props'),
    }, indent=2))
    try:
        request("/v1/models", authenticated=False)
        raise RuntimeError("Unauthenticated model access was accepted")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        rows.append({"check": "unauthenticated_access", "http_status": error.code, "passed": True})
    models = request("/v1/models")
    if 'gemma-4-31b' not in [model['id'] for model in models['data']]:
        raise RuntimeError('Required public model alias is absent')
    rows.append({'check': 'model_alias', 'passed': True})

    prompts = {
        "arithmetic": ("What is 19 + 23? Reply with just the number.", 64),
        "korean": ("한국어로 공유 메모리가 무엇인지 두 문장으로 설명해 주세요.", 256),
        "python": ("Write only a Python function named square taking x and returning x * x. No explanation.", 256),
        "structured_json": ('Return only valid JSON, without a code fence, with name "halo", enabled true, and ports [8080, 8081].', 128),
        "long_context": ("Reference passage:\n" + "Shared memory stores data used by the CPU and GPU.\n" * 500
                         + "\nThe verification code is HALO314159. Reply with only that verification code.", 64),
    }
    for name, (prompt, limit) in prompts.items():
        result = request("/v1/chat/completions", {
            "model": "gemma-4-31b", "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "seed": 1234, "max_tokens": limit,
            "chat_template_kwargs": {"enable_thinking": False}, "reasoning_budget_tokens": 0,
            "cache_prompt": False,
        })
        choice = result["choices"][0]
        content = choice["message"].get("content") or ""
        passed = choice["finish_reason"] == "stop" and bool(content.strip())
        if name == "arithmetic":
            passed &= content.strip().strip(".") == "42"
        elif name == "korean":
            passed &= len(re.findall("[가-힣]", content)) >= 10
        elif name == "python":
            blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", content, re.S)
            try:
                tree = ast.parse(blocks[0] if blocks else content.strip())
                passed &= any(isinstance(node, ast.FunctionDef) and node.name == "square" for node in tree.body)
            except SyntaxError:
                passed = False
        elif name == "long_context":
            passed &= "HALO314159" in content and result["usage"]["prompt_tokens"] >= 4096
        elif name == "structured_json":
            try:
                passed &= json.loads(content) == {"name": "halo", "enabled": True, "ports": [8080, 8081]}
            except ValueError:
                passed = False
        rows.append({"check": name, "passed": bool(passed), "response": result})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
    # Leave the template and reasoning settings unspecified: exercise the default.
    result = request('/v1/chat/completions', {
        'model': 'gemma-4-31b', 'messages': [{'role': 'user', 'content': 'What is 19 + 23?'}],
        'temperature': 0, 'seed': 1234, 'max_tokens': 512, 'cache_prompt': False,
    })
    choice = result['choices'][0]
    message = choice['message']
    reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
    passed = (choice['finish_reason'] == 'stop' and '42' in (message.get('content') or '')
              and bool(reasoning.strip()))
    rows.append({'check': 'default_reasoning', 'passed': bool(passed), 'response': result})
    print(f"default_reasoning: {'PASS' if passed else 'FAIL'}", flush=True)
    payload = {'model': 'gemma-4-31b', 'messages': [{'role': 'user', 'content': 'Reply with exactly: HALO_STREAM_OK'}],
               'temperature': 0, 'max_tokens': 64, 'stream': True,
               'chat_template_kwargs': {'enable_thinking': False}, 'cache_prompt': False}
    req = urllib.request.Request(base + '/v1/chat/completions', json.dumps(payload).encode(), headers)
    events, done = [], False
    with urllib.request.urlopen(req, timeout=600) as response:
        for line in response:
            if not line.startswith(b'data: '):
                continue
            data = line[6:].strip()
            if data == b'[DONE]':
                done = True
            else:
                events.append(json.loads(data))
    choices = [choice for event in events for choice in event.get('choices', [])]
    content = ''.join(choice.get('delta', {}).get('content') or '' for choice in choices)
    passed = done and 'HALO_STREAM_OK' in content and any(c.get('finish_reason') == 'stop' for c in choices)
    rows.append({'check': 'streaming_eos', 'passed': bool(passed), 'events': events, 'done': done})
    print(f"streaming_eos: {'PASS' if passed else 'FAIL'}", flush=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    if not all(row["passed"] for row in rows):
        raise SystemExit("Serving checks failed; inspect the retained responses")


if __name__ == "__main__":
    main()
