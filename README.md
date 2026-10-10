# Gemma 4 31B · Strix Halo

**ASUS ROG Flow Z13 (2025)** · Vulkan/HIP benchmarks, Compose stack, kernel patches.

![Generation throughput](assets/overview.png)

## Configuration

| Hardware | Software |
|---|---|
| Ryzen AI Max+ 395 · Radeon 8060S | Fedora 44 · llama.cpp v0.6.0 |
| 64 GiB · 8000 MT/s | Vulkan · Q4_K_M · Q8 assistant |
| 16 GiB GPU reservation | MTP-4 · F16 KV · 8K context |

## Quantization

![Quantization](assets/quantization.png)

## Long context

![Long-context latency](assets/long-context.png)

## Concurrency

![Concurrent throughput](assets/concurrency.png)

**Status:** optimization paused. Candidates require quality and paired validation; the original preset remains deployed. NPU acceleration is unvalidated.

## Reproduce

[Setup](docs/setup.md) · [Methodology](docs/methodology.md) · [Experiments](docs/experiments.md) · [Data](data/README.md)

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-charts.txt
.venv/bin/python tools/render_charts.py
```

MIT licensed. [Third-party notices](THIRD_PARTY_NOTICES.md).
