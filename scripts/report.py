"""Derive the human-readable benchmark report from actual saved measurements."""

import json
from pathlib import Path


def main() -> None:
    local = json.loads(Path("benchmarks/results/local.json").read_text())
    neural = json.loads(Path("benchmarks/results/neural.json").read_text())
    load = json.loads(Path("benchmarks/results/load.json").read_text())
    lines = [
        "# Recorded measurements",
        "",
        "Generated from the checked-in JSON runs. "
        "All values below were measured; this report contains no estimated benchmark scores.",
        "",
        "## Conditions",
        "",
        f"Local run: {local['measured_at']}. Neural run: {neural['measured_at']}.",
        "Eight authored notes and twelve co-authored questions; document-level judgments. "
        "Three repetitions per query/configuration. Chunk size 40 word tokens, overlap 8, "
        "context budget 2,200 UTF-8 bytes. LLM generation is extractive for both profiles.",
        "",
        "Latency excludes HTTP transport, process startup, model loading and index build; "
        "index/ingestion durations are separately recorded in JSON. Cold P95 uses the first "
        "pass through the twelve questions; warm P95 uses the remaining passes. "
        "This sample is too small to support tail-latency SLOs.",
        "",
    ]
    for name, data in [("Local LSA / lexical", local), ("Pinned MiniLM / cross-encoder", neural)]:
        lines += [f"## {name}", ""]
        for p in data["pipelines"]:
            lines.append(
                f"- **{p['name']}**: Recall@5 {p['recall_at_5']:.3f}; "
                f"MRR {p['mrr']:.3f}; nDCG@5 {p['ndcg_at_5']:.3f}; "
                f"reference token-F1 proxy {p['token_f1_proxy']:.3f}; "
                f"cold P95 {p['cold_latency']['p95_ms']:.2f} ms; "
                f"warm P95 {p['warm_latency']['p95_ms']:.2f} ms."
            )
        lines.append("")
    lines += ["## HTTP concurrency experiment", "", load["scope"] + ".", ""]
    for row in load["runs"]:
        lines.append(
            f"- Concurrency {row['concurrency']}: {row['requests']} requests; "
            f"statuses {row['statuses']}; P50 {row['p50_ms']:.2f} ms; "
            f"P95 {row['p95_ms']:.2f} ms; P99 {row['p99_ms']:.2f} ms; "
            f"observed throughput {row['throughput_requests_per_second']:.1f} requests/s; "
            f"retrieval cache hit rate {row['cache_hit_rate']:.1%}."
        )
    lines += [
        "",
        "These are short loopback bursts with mixed/warm caches, not a sustained "
        "production load test. Concurrency and cache state both change between levels, "
        "so throughput differences cannot be attributed to concurrency alone.",
        "",
        "## Interpretation",
        "",
        "The fixture is easy for dense retrieval. Hybrid and neural reranking do not "
        "establish a recall gain. The cross-encoder adds substantial computation, while "
        "generic decomposed subqueries can weaken global rank ordering. The local "
        "follow-up example loses relevant evidence when rewriting is disabled. "
        "Verification ablations mostly show equal exact-support proxies because the "
        "writer already copies source text; this does not evaluate hallucination "
        "detection on freely generated answers.",
        "",
        "The practical next benchmark needs independently judged documents, harder "
        "distractors, domain-specific multi-hop queries, human correctness assessment, "
        "and sustained networked load. Do not convert these results into a production "
        "accuracy, cost-saving, or latency claim.",
        "",
        "## Reproducibility",
        "",
        f"Corpus SHA-256: `{local['corpus_sha256']}`.",
        "",
        f"Dataset SHA-256: `{local['dataset_sha256']}`.",
        "",
        "Model commits: `configs/neural-models.json`. Configurations: "
        "`experiments/ablations.json`. Full per-question answers, relevance scores, "
        "timings, dependency versions, and model settings are retained in "
        "`benchmarks/results/local.json` and `neural.json`.",
    ]
    Path("docs/benchmark-report.md").write_text("\n".join(lines) + "\n")
    print("Saved docs/benchmark-report.md from recorded measurements.")


if __name__ == "__main__":
    main()
