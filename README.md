# Gemma 4 31B · Strix Halo

**ROG Flow Z13 (2025)** · Ryzen AI Max+ 395 · Radeon 8060S · 64 GiB

![Generation](assets/overview.png)

## Stack

| Component | Version |
|---|---|
| Fedora / Linux | 44 / 7.2.9 |
| llama.cpp | v0.6.0 · `d812350` |
| ROCm | 10.1.0 |
| Mesa / RADV | 26.2.3 |
| Vulkan loader | 1.4.341.0 |
| GCC / CMake | 16.2.1 / 4.3.0 |
| Docker / Compose | 29.7.2 / 5.5.1 |

Q4_K_M · Q8 assistant · MTP-4 · F16 KV · 8K context

![Quantization](assets/quantization.png)

![Context](assets/long-context.png)

![Concurrency](assets/concurrency.png)

[Setup](docs/setup.md) · [Metrics](docs/methodology.md) · [Experiments](docs/experiments.md) · [Data](data/README.md) · [License](LICENSE)
