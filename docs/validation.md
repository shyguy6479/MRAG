# Validation and release boundaries

## Exercised locally

- End-to-end ingestion, retrieval, reranking, context, agent, verification, HTTP
  endpoints and real chunk citations.
- Deterministic and API tests, HTTP provider mocks, limits, parsing/chunking,
  expired-job recovery, caches, arithmetic, filters, and SQLite migration round-trips.
- Actual pinned sentence-transformer and cross-encoder inference, including all
  ten neural experiment configurations. Scores are measured, not simulated.
- Qdrant adapter upsert/filter/search/delete against its embedded in-memory backend.
  This does not validate a networked Qdrant server.
- React type checking and production build; browser review of research, sources,
  trace, library and experiments; HTTP smoke and short concurrency runs.

Actual measurements are under `benchmarks/results/`; screenshots under
`docs/screenshots/`. Final command outcomes are recorded in `docs/build-report.md`.

## Not exercised here

Docker is not installed. Container builds, PostgreSQL/Redis integration, Celery
recovery against those services, networked Qdrant, and the Grafana stack have not
run here. CI jobs exist for these gates; they are configured, not asserted to have
passed remotely. The service integration test skips without explicit connection URLs.

No paid generation provider was called. Success/retry/failure paths were tested
with HTTP mocks; validate the actual chosen endpoint before deployment.

## Deployment gate

Run container and external-service tests, verify server/client compatibility, and
pin/review container digests through your registry process. Apply credentials via
a secrets manager, terminate TLS at ingress, keep infrastructure private, and
configure actual provider pricing plus provider-side spend limits.

This is one trusted workspace. A shared key is not user authentication or document
authorization. Add user/tenant ACLs before serving mutually untrusted users.
Define retention, backups, restore drills, and audited deletion requirements.

Test larger/hostile PDFs, sustained traffic, queue recovery, resource exhaustion,
and model failures. Celery hard limits bound ingestion tasks; local CPU threads
cannot be forcibly interrupted by an asyncio timeout. Basic injection patterns
and size limits are not complete parser isolation. Establish independent relevance
and answer judgments before claiming an accuracy or latency objective.

## Deliberate trade-offs

BM25/LSA indexes rebuild per process and consume corpus-sized memory. Qdrant filters
use database-valid IDs; large corpora should use server-side ACL/version payloads.
One corpus revision row serializes mutations for simpler correctness. Missed leases
can leave unused external vectors, which stay non-searchable until maintenance purge.

Memory selects recent user topics; concurrent turns are ordered by completion,
not a distributed conversation lock. Section-aware chunking uses headings rather
than embedding change-point detection. Chunk lengths use words; context limits
use a conservative byte bound. Lexical support is not entailment. These choices
remain visible and replaceable through the module interfaces.


## Workspace redesign validation — 5 October 2026

The additive workspace API adapters passed the complete backend suite: **45 passed,
1 skipped** (optional service integration), with one dependency deprecation warning.
New checks cover actual retrieval score channels and filters, bounded/validated
search requests, persisted conversation summaries, endpoint authentication and
allowlisted benchmark results. Ruff and mypy passed.

The five frontend tests cover Prometheus parsing, route-scoped histogram aggregation,
empty/unbounded quantiles, weighted stage means and request-rate sampling/reset.
TypeScript and the production Vite build passed after the responsive and keyboard
fixes. This does not constitute a browser automation regression suite.

Visual inspection covered every major page at 1440×900, 1728×1117, 1920×1080 and
1280×800, plus 390×844 phone views and 1024×768 research/evidence sheets. Browser
interaction checks and remaining UI boundaries are documented in
[interface-design.md](interface-design.md). Evidence is saved under
`docs/screenshots/qa/`. No new benchmark quality claims or production deployment
claims are made by the redesign.
