# Gemma 4 31B · Strix Halo

**ASUS ROG Flow Z13 (2025)**

![Generation throughput](assets/overview.png)

## Hardware

| Component | Specification |
|---|---|
| APU | Ryzen AI Max+ 395 |
| GPU | Radeon 8060S · gfx1151 |
| Memory | 64 GiB · 8000 MT/s · 16 GiB GPU reservation |

## Software

| Component | Version |
|---|---|
| OS / kernel | Fedora 44 / Linux 7.2.9 |
| llama.cpp | v0.6.0 · `d812350` |
| ROCm SDK | 10.1.0 · gfx1151 |
| Mesa / RADV | 26.2.3 |
| Vulkan loader | 1.4.341.0 |
| GCC / CMake | 16.2.1 / 4.3.0 |
| Docker / Compose | 29.7.2 / 5.5.1 |

Q4_K_M · Q8 assistant · MTP-4 · F16 KV · 8K context

## Quantization

![Quantization](assets/quantization.png)

## Long context

![Long-context latency](assets/long-context.png)

## Concurrency

![Concurrent throughput](assets/concurrency.png)

[Setup](docs/setup.md) · [Methodology](docs/methodology.md) · [Experiments](docs/experiments.md) · [Data](data/README.md) · [Licenses](THIRD_PARTY_NOTICES.md)
