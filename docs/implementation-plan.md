# Phased implementation plan

Each phase must have a runnable acceptance check. Do not advance past a failing
core test. Implementations are distinguished from optional adapters that have not
been exercised against external services.

1. **Architecture and foundation:** package, validated settings, domain contracts,
   provider protocols, API lifecycle, health, request IDs, database bootstrap,
   Docker / CI foundation. Gate: settings, contracts, health and error tests.
2. **Ingestion:** durable jobs, PDF/HTML/Markdown/text parsing, provenance, three
   chunking strategies, idempotent indexing and deletion. Gate: parser, job,
   metadata, upload-size and persistence tests.
3. **Dense and sparse retrieval:** real local LSA baseline, BM25, optional neural
   embedding and Qdrant adapter, metadata filters. Gate: known-relevant retrieval
   and strict filter tests.
4. **Fusion:** independently implemented RRF with deterministic tie-breaking.
   Gate: known ranks, duplicate IDs, empty lists, weights and top-k tests.
5. **Reranking:** lexical baseline and optional cross-encoder with explicit
   degradation. Gate: reordering and provider-failure behavior.
6. **Query intelligence:** deterministic routing, selective memory, rewriting,
   bounded decomposition. Gate: follow-ups, comparisons and ordinary conversation.
7. **Agent and tools:** bounded workflow, safe calculator, document / metadata /
   section tools, trace records, token and cost accounting. Gate: limits and
   rejected unsafe expressions.
8. **Grounding:** diverse context, exact-source citations, verification and
   evidence insufficiency. Gate: no fabricated citations, context budget and
   unsupported-answer rejection.
9. **Evaluation:** authored corpus and relevance judgments, retrieval metrics,
   named generation proxies, saved reproducible runs. Gate: hand-computed metrics.
10. **Operations:** Redis cache, revision invalidation, rate limiting, retries,
    traces, Prometheus and Grafana. Gate: failures, stale caches and metrics.
11. **Frontend and deployment:** React research workspace, evidence inspector,
    document management, run traces, evaluation results and full Compose stack.
    Gate: production frontend build, API integration, container smoke check when
    Docker is available.
12. **Experiments and presentation:** retrieval / reranking / chunking / rewrite /
    decomposition / verification ablations, latency and load tests, actual saved
    results, architecture decisions and interview guide. Gate: complete offline
    test suite, lint, types, benchmark output schema and documentation audit.

## Explicit non-goals for the first release

Multi-tenant access control, web crawling, arbitrary agent code execution,
multimodal / graph retrieval, calibrated probabilities, unlimited documents,
distributed sparse indexing, high availability, and unattended public deployment.
