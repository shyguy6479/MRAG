# Build and validation report

Recorded on 4 October 2026. This report distinguishes completed implementation
from infrastructure that still needs execution in a deployment environment.

## Delivered

All twelve implementation phases have source, documentation and applicable local
checks. The working application includes durable ingestion, three chunkers,
BM25 and dense retrieval, custom RRF, neural and lexical reranking, selective
conversation memory, decomposition, bounded tools, source citations, conservative
claim verification, revision-aware caching, telemetry, a React workspace, and
reproducible evaluation scripts. Deployment configuration and CI are included.

The running local profile uses SQLite, corpus-fitted LSA, lexical reranking and
exact-source excerpts. It needs no API key. The optional neural profile was
separately exercised with actual pinned MiniLM and cross-encoder weights.
Hosted LLM generation is configurable and was tested with HTTP mocks.

## Recorded checks

- `pytest -q`: **43 passed, 1 skipped**, in 3.50 seconds. The skipped test requires
  explicit PostgreSQL/Redis integration URLs. An upstream Starlette/httpx
  deprecation warning remains; it does not fail the suite.
- `ruff check src tests scripts workers migrations`: passed.
- `ruff format --check src tests scripts workers migrations`: passed.
- `mypy src`: passed, no issues in 30 source files.
- `npm run build --prefix apps/web`: passed TypeScript and Vite production build.
  The original build sizes were 266.81 kB JavaScript and 31.97 kB CSS; the
  interface revision below supersedes these sizes.
- SQLite Alembic upgrade/downgrade: exercised successfully during implementation.
- Embedded Qdrant upsert, filtering, search and deletion: passed in the test suite.
- HTTP smoke test: passed document creation, asynchronous ingestion, filtered
  retrieval, citation checks and deletion of the disposable document.
- HTTP concurrency experiment: all **36 requests returned 200** at concurrency
  1, 4 and 8. See the saved measurements and their small-sample limitations.
- Local and neural benchmark runners: completed ten configurations, twelve
  questions and three repetitions per profile; **720 query/configuration runs**
  in total. The report is generated from the saved JSON measurements.
- Browser review: verified the research workspace, real source citations, action
  trace, knowledge library and recorded experiment chart. Screenshots are saved
  in `docs/screenshots/`; the interface reads actual API responses.

The algorithm and failure tests cover fusion, strict filters, context limits,
input/file limits, cached revisions, job recovery, safe arithmetic, provider
retry/failure behavior, grounding, and rejection of fabricated citation references
even when the optional claim-verification ablation is disabled.

## Remaining release gates

Docker is unavailable on this machine. Container builds and the networked
PostgreSQL/Redis/Celery/Qdrant/Grafana stack have **not** been run here. The GitHub
Actions workflow defines service integration and container smoke gates; no remote
CI pass is claimed. The base and neural Compose profiles require validation on a
Docker host before deployment.

No paid LLM endpoint, sustained capacity test, independent answer-quality study,
multi-tenant authorization, high-availability setup, or backup/restore drill was
performed. See [validation boundaries](validation.md) and
[recorded measurements](benchmark-report.md) for the specific limits and next gates.

## Reproduction

Follow the [README](../README.md) to create an environment and seed the corpus.
Run the quality commands there, then `python scripts/benchmark.py`, optionally
`python scripts/benchmark.py --neural`, and `python scripts/report.py`. Neural
model revisions are recorded in `configs/neural-models.json`.

The source archive excludes installed dependencies, downloaded model weights,
local database/conversation data, build caches and private environment files.
These are recreated through the documented setup commands.

## Interface revision — 5 October 2026

The latest redesign replaces the decorative hero with a compact research workspace,
a reusable design system, seven stable routes, a keyboard command menu and a
contextual evidence inspector. Search Explorer exposes actual ranking channels;
Experiments and Evaluations read stored runs; Observability samples live metrics.

Four additive presentation endpoints expose existing retrieval, conversation and
benchmark data. No retrieval/generation algorithm or database schema changed.
See [interface notes](interface-design.md) for the precise contracts and gaps.

Verification: 45 backend tests passed, one optional service test skipped; Ruff,
mypy, five frontend metric tests and the TypeScript/Vite build passed. All major
pages were visually reviewed at the four requested desktop sizes, with additional
phone and tablet checks. Screenshots include real research and stored measurements.
Container deployment and the remaining release gates above are still unverified.
