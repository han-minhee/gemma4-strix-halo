# Experiments

![MTP depth](../assets/speculation.png)

![Kernel dispatch](../assets/kernel-boundary.png)

| Approach | Result |
|---|---|
| MTP depth | Reference: 4 |
| Confidence / adaptive MTP | No qualifying gain |
| 16-column dispatch | MTP-8: 19.02 tok/s; below MTP-4 |
| HIP wide attention | Unqualified |
| CPU-only | 4.10 tok/s · synthetic |
| Q4 assistants | About +2% |
| Affinity / polling | 23.62–23.72 median tok/s |
| ROCmFP4, plain | 11.97 Vulkan / 10.95 HIP aggregate tok/s |
| ROCmFPX MTP | Validation failed |
| Four-slot HIP | 4800 MiB KV allocation failed |
| NPU | No 31B target/assistant execution path |

[Patches](../patches/) · [Gates](methodology.md) · [Source pins](../experiments/sources.json)
