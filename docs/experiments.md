# Optimization experiments

## Speculation

![MTP draft-depth screen](../assets/speculation.png)

Depth 4 won the 1–8 screen. Confidence filtering raised acceptance to 80.9% but reduced throughput; the best filtered case reached 24.52 aggregate tok/s versus reference brackets of 25.28 / 24.72.

Adaptive MTP supported this Gemma assistant but produced no qualifying gain. Its chained-head path requires independent draft memory and does not apply to Gemma's shared target KV arrangement.

## Kernel work

![Vulkan dispatch boundary and patched MTP-8 performance](../assets/kernel-boundary.png)

Vulkan switches multiplication paths beyond eight verification columns. Extending matrix-vector dispatch to 16 columns passed selected numerical checks and almost doubled MTP-8 throughput, but did not beat MTP-4. Other row-tile changes also missed the 5% threshold.

HIP profiling attributed 46.14% of recorded kernel time to one Q4_K matrix kernel and 25.24% to two matrix-vector variants. Instrumentation mixed warmup, prefill, and decode; these traces are diagnostic.

The 512-wide HIP attention patch built, but its overall correctness stage was rejected. It remains unqualified. All patches are isolated in [`patches/`](../patches/); upstream numerical tolerances were retained.

## Other approaches

| Approach | Measured finding | Decision |
|---|---|---|
| CPU-only | 4.10 tok/s in initial synthetic benchmark | Full GPU offload preferred |
| Current upstream / native HIP | No qualifying interactive gain; HIP generally slower | Retain Vulkan reference |
| Q4 assistants | About 2% aggregate improvement | Retain Q8 assistant |
| CPU affinity / polling | 23.62–23.72 median tok/s | Retain defaults |
| ROCmFP4 STRIX_LEAN | 11.97 Vulkan / 10.95 HIP aggregate tok/s, plain decode | Slower than deployed MTP |
| ROCmFPX MTP repairs | Model-level assertions or conversation-cache failures | Rejected |
| HIP, four slots | 4800 MiB KV allocation failed before inference | Capacity experiment unfinished |
| NPU | No executable Linux 31B target + assistant path established | No NPU speedup claimed |

Whole-model CPU and mixed CPU/GPU execution were slower in initial placement tests. CPU drafting failed initialization because the assistant shared GPU-resident target KV tensors.

## Remaining work

Complete coding/strict-output quality gates, investigate HIP wide-attention qualification, repair thermal stabilization, and run ten-pair finalist comparisons plus sustained-load/restart validation. Sampling, microbatch refinement, managed-memory capacity, and EPP experiments remain unfinished. No new interactive, long-context, or throughput preset was deployed.

Sources: [llama.cpp v0.6.0](https://github.com/ggml-org/llama.cpp/tree/v0.6.0), [adaptive MTP proposal](https://github.com/ggml-org/llama.cpp/pull/27210), [ROCmFPX](https://github.com/charlie12345/ROCmFPX), [Ryzen AI Linux support](https://ryzenai.docs.amd.com/en/main/llm_linux.html), [FastFlowLM](https://github.com/ROCm/FastFlowLM).
