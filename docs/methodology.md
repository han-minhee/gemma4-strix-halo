# Measurement protocol

## Workloads

| Suite | Inputs | Outputs | Repetitions |
|---|---|---|---|
| Interactive | English prose, Python, Korean | 128 fixed tokens | 1 warmup + 3 timed / prompt |
| Long context | 4096 / 8192 / 16384 actual tokens; cold and reused prefixes | 128 fixed tokens | 1 warmup + 3 timed / workload |
| Concurrency | 1 / 2 / 4 simultaneous requests; 8192 context tokens per request | 128 tokens / request | 1 warmup + 3 timed batches |

Fixed-length comparisons disable reasoning, use greedy sampling, and ignore EOS. Service canaries separately check natural EOS, default reasoning, authentication, Korean, code, retrieval, and streaming token accounting.

Cases run serially. Candidate order is randomized where configured, with baseline brackets. No downloads, conversions, or other GPU work run during timed batches.

## Metrics

| Metric | Definition |
|---|---|
| Median decode | Median `(predicted_n − 1) / generation_seconds` across requests |
| Aggregate decode | Sum of generated tokens excluding first tokens / summed generation time |
| Aggregate wall throughput | All generated tokens / summed batch wall time; includes request overhead |
| TTFT | Client time from request start to first streamed content |
| Completion | Client time from request start to completed response |
| p95 | Linear interpolation of sorted observations |

Streaming chunks can contain multiple speculative tokens. Chunk-arrival gaps do not measure individual internal GPU token latency. Small screening samples produce descriptive percentiles, not robust tail estimates. Package-power readings are not wall-plug measurements.

## Promotion gates — incomplete

Finalists require ten randomized adjacent baseline/candidate pairs, ≥5% primary improvement, a paired 95% confidence interval excluding zero, and ≤5% secondary latency regression. Backend correctness, service canaries, sustained load, restart recovery, and no GPU resets are additional requirements.

Changed quantization requires ≤1% relative perplexity increase separately on fixed English/Korean corpora, ≤2 percentage-point coding-score loss, and no new strict JSON or retrieval failures.

The fixed perplexity samples produced unusually high absolute scores. An independent logit probe reproduced a chunk score, but this remains a narrow relative comparison. No general quality equivalence is claimed.

## State at pause

No follow-up preset completed all gates. The thermal plateau check rejected phase-dependent temperature cycles and needs review before final paired runs. Early smoke checks extracted fenced JSON; those checks establish semantic content only. Later checks parse the complete response as strict JSON.
