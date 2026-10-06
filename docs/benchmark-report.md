# Recorded measurements

Generated from the checked-in JSON runs. All values below were measured; this report contains no estimated benchmark scores.

## Conditions

Local run: 2026-10-04T12:48:03.502070+00:00. Neural run: 2026-10-04T12:49:14.893529+00:00.
Eight authored notes and twelve co-authored questions; document-level judgments. Three repetitions per query/configuration. Chunk size 40 word tokens, overlap 8, context budget 2,200 UTF-8 bytes. LLM generation is extractive for both profiles.

Latency excludes HTTP transport, process startup, model loading and index build; index/ingestion durations are separately recorded in JSON. Cold P95 uses the first pass through the twelve questions; warm P95 uses the remaining passes. This sample is too small to support tail-latency SLOs.

## Local LSA / lexical

- **Dense (LSA)**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.463; cold P95 2.28 ms; warm P95 0.81 ms.
- **BM25**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.471; cold P95 1.15 ms; warm P95 1.16 ms.
- **Hybrid RRF**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.461; cold P95 2.08 ms; warm P95 1.49 ms.
- **Hybrid + lexical reranker**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.465; cold P95 2.04 ms; warm P95 1.18 ms.
- **Agentic**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.472; cold P95 5.23 ms; warm P95 2.02 ms.
- **Fixed chunks**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.484; cold P95 4.44 ms; warm P95 1.67 ms.
- **Recursive chunks**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.493; cold P95 4.67 ms; warm P95 1.39 ms.
- **Rewrite off**: Recall@5 0.917; MRR 0.875; nDCG@5 0.886; reference token-F1 proxy 0.434; cold P95 5.26 ms; warm P95 1.94 ms.
- **Decomposition off**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.477; cold P95 2.11 ms; warm P95 1.22 ms.
- **Verification off**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.472; cold P95 3.60 ms; warm P95 1.08 ms.

## Pinned MiniLM / cross-encoder

- **Dense (MiniLM)**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.481; cold P95 9.83 ms; warm P95 1.00 ms.
- **BM25**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.471; cold P95 1.28 ms; warm P95 0.79 ms.
- **Hybrid RRF**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.480; cold P95 6.62 ms; warm P95 0.82 ms.
- **Hybrid + cross-encoder**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.488; cold P95 206.21 ms; warm P95 0.91 ms.
- **Agentic**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.463; cold P95 296.42 ms; warm P95 1.18 ms.
- **Fixed chunks**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.463; cold P95 359.08 ms; warm P95 55.58 ms.
- **Recursive chunks**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.501; cold P95 464.08 ms; warm P95 1.27 ms.
- **Rewrite off**: Recall@5 1.000; MRR 0.917; nDCG@5 0.938; reference token-F1 proxy 0.425; cold P95 323.65 ms; warm P95 1.19 ms.
- **Decomposition off**: Recall@5 1.000; MRR 1.000; nDCG@5 1.000; reference token-F1 proxy 0.488; cold P95 160.02 ms; warm P95 0.95 ms.
- **Verification off**: Recall@5 1.000; MRR 0.958; nDCG@5 0.969; reference token-F1 proxy 0.463; cold P95 302.86 ms; warm P95 1.10 ms.

## HTTP concurrency experiment

HTTP loopback, small authored corpus, mixed/warm caches, no LLM calls.

- Concurrency 1: 12 requests; statuses {'200': 12}; P50 4.31 ms; P95 7.24 ms; P99 9.47 ms; observed throughput 233.6 requests/s; retrieval cache hit rate 0.0%.
- Concurrency 4: 12 requests; statuses {'200': 12}; P50 6.65 ms; P95 9.92 ms; P99 10.13 ms; observed throughput 548.1 requests/s; retrieval cache hit rate 100.0%.
- Concurrency 8: 12 requests; statuses {'200': 12}; P50 11.63 ms; P95 19.69 ms; P99 20.20 ms; observed throughput 537.6 requests/s; retrieval cache hit rate 100.0%.

These are short loopback bursts with mixed/warm caches, not a sustained production load test. Concurrency and cache state both change between levels, so throughput differences cannot be attributed to concurrency alone.

## Interpretation

The fixture is easy for dense retrieval. Hybrid and neural reranking do not establish a recall gain. The cross-encoder adds substantial computation, while generic decomposed subqueries can weaken global rank ordering. The local follow-up example loses relevant evidence when rewriting is disabled. Verification ablations mostly show equal exact-support proxies because the writer already copies source text; this does not evaluate hallucination detection on freely generated answers.

The practical next benchmark needs independently judged documents, harder distractors, domain-specific multi-hop queries, human correctness assessment, and sustained networked load. Do not convert these results into a production accuracy, cost-saving, or latency claim.

## Reproducibility

Corpus SHA-256: `2d7e35fc45f85902ce0fb6324c81d8e2c6d20c4401a72fec53d56c74f1d3adfd`.

Dataset SHA-256: `950248e5bd93e89e34f66b7af496685af42d31a62a3e71ad01ea0b0a4fc8870c`.

Model commits: `configs/neural-models.json`. Configurations: `experiments/ablations.json`. Full per-question answers, relevance scores, timings, dependency versions, and model settings are retained in `benchmarks/results/local.json` and `neural.json`.
