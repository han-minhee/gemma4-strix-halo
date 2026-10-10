# Metrics

## Protocol

| Suite | Input | Output | Timed runs |
|---|---|---|---|
| Interactive | English, Python, Korean | 128 tokens | 3 / prompt |
| Context | 4K / 8K / 16K; cold/reused | 128 tokens | 3 / case |
| Concurrency | 1 / 2 / 4 clients; 8K context/client | 128 tokens/client | 3 batches |

One discarded warmup. Greedy decoding; reasoning off; fixed length. Serial runs with baseline brackets. Natural EOS and default reasoning checked separately.

## Definitions

| Metric | Calculation |
|---|---|
| Median decode | Median `(tokens − 1) / generation time` |
| Aggregate decode | `Σ(tokens − 1) / Σgeneration time` |
| Wall throughput | `Σtokens / Σbatch wall time` |
| TTFT | Request → first content |
| Completion | Request → final response |
| p95 | Interpolated 95th percentile |

Stream chunks may contain multiple tokens. Small-sample p95 is descriptive. Package power excludes wall-plug losses.

## Gates

| Check | Requirement |
|---|---|
| Performance | ≥5% gain; ten pairs; positive 95% paired interval |
| Secondary latency | ≤5% regression |
| Quantization | ≤1% relative PPL increase/language; ≤2 pp coding loss |
| Correctness | Backend tests, JSON, retrieval, EOS, restart, sustained load; no GPU resets |

Final validation incomplete. Thermal plateau check failed. Absolute PPL scores were unusually high. Early JSON smoke accepted fences; later checks parse the complete response.
