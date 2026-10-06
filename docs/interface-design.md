# MRAG research workspace

Interface revision: 6 October 2026. The audit and phased implementation plan are in
[ui-redesign-audit.md](ui-redesign-audit.md).

## Design and navigation

The interface uses white surfaces, blue typography and cobalt accents, DM Sans text and
IBM Plex Mono measurements, with system font fallbacks. Research is a compact
workspace: question composer, quick actions, recent saved sessions and live index
counts. Responses are readable documents with inline evidence references.

The shell has a collapsible 248px sidebar (68px collapsed), a 56px toolbar and a
keyboard command menu. Stable routes are `/research`, `/knowledge`, `/search`,
`/experiments`, `/evaluations`, `/observability` and `/settings`. A saved research
session uses `/research?session=<id>`. Browser back/forward and direct refresh use
these URLs; the web server must provide the existing SPA fallback.

The contextual inspector is 380px on ordinary desktop layouts and 400px on larger
screens. Tablet layouts collapse it into a right sheet. On phones, navigation is
a drawer, research is one column and evidence opens as a bottom sheet.

## Components and state

`apps/web/src/components/ui` holds reusable buttons, labeled inputs, selects,
badges, tabs, dialogs, sheets, tables, metrics, charts, skeletons, error/empty states
and toast feedback. Shared tokens and responsive rules live in `styles.css`.
Research, evidence, documents and trace components have separate typed modules.

`AppShell` owns navigation and command UI. `useWorkspace` owns server document,
system and recent-session state. `useResearch` owns research requests, cancellation,
loaded turns and source selection. `useRuns` reads recorded benchmark artifacts;
`useMetrics` samples Prometheus counters. Non-research routes are lazy loaded;
charts are bundled with the analytical routes. No new runtime dependency was added.
Long chunk lists are paginated. Narrow data tables scroll within their containers.

Dialogs render in a portal, contain keyboard focus, close with Escape and restore
focus. Tabs and the command results support arrow keys. Mobile icon actions retain
accessible names. Visible focus styles and reduced-motion CSS are included. This
is practical accessibility work, not a formal WCAG conformance certification.

## Workflows

- Research modes map to existing retrieval/rewrite/decomposition options. Enter
  submits; Shift+Enter inserts a line. Source selection uses indexed document IDs.
- Citations preview on hover or focus and open the precise source in the inspector.
  Sources, Retrieval, Agent and Trace expose actual evidence, queries, safe tool
  summaries, recorded stage durations, model/provider labels, token counts and cost.
- Knowledge Base provides filters, upload, document metadata, searchable chunks and
  explicit deletion confirmation. Upload shows the real queued/processing/indexed/
  failed statuses, and explains the absence of detailed ingestion-stage telemetry.
- Search Explorer calls retrieval without generation and shows actual dense, BM25,
  RRF and reranker channels, top-K, document/section filters and cache information.
- Experiments reads stored local/neural runs, configurations, questions and failures.
  New Experiment explains the actual CLI commands because no job-launch API exists.
- Evaluations compares selected recorded pipelines and computes deltas from their
  stored values. Labels preserve Recall@5, nDCG@5 and named generation proxies.
- Observability reads live `/metrics` and `/ready`. Request rate needs two samples;
  P95 is explicitly a histogram estimate. Stage charts show weighted observed
  means. Saved traces are the latest response per conversation, not a full trace store.
- Settings shows the configured capabilities and supports a same-origin workspace
  API key stored only in session storage. It does not pretend to provision accounts,
  change server models or create additional workspaces.

## Additive API presentation adapters

`src/atlasrag/workspace_routes.py` adds four endpoints, registered by the existing
API. Existing contracts, algorithms, database schema and authentication middleware
are unchanged. [openapi.json](openapi.json) includes the additions.

- `POST /search`: accepts the existing query fields, bounded top-K and filters;
  restricts strategy to dense, sparse, hybrid or hybrid_reranked. Returns ranked
  hit objects with channel scores, candidates considered, cache status, warnings,
  elapsed milliseconds, corpus revision and configured retrieval providers. It
  calls the existing engine snapshot/search functions and applies the query timeout.
- `GET /conversations`: returns at most 50 recent conversations, with latest
  question, UTC timestamp, turn/source counts and the latest saved response. A SQL
  window query avoids loading complete histories for the navigation list.
- `GET /evaluation-runs`: lists available local/neural benchmark artifact summaries.
- `GET /evaluation-runs/{run_id}`: returns an allowlisted artifact plus authored
  question labels; unknown or absent runs return 404. IDs are never filesystem paths.

These endpoints use the same shared workspace-key boundary as existing routes.
Benchmark adapters are read-only; they do not launch training or evaluation jobs.
The Docker build context includes only the allowlisted local/neural result JSON
files from the results directory so recorded views can work in the packaged image.
The container build itself remains unverified on this machine.

## Honest capability boundaries

The default local profile generates exact evidence excerpts. It is labeled as such.
Exact source support is a heuristic, not calibrated confidence or semantic entailment.
The saved benchmark is eight authored notes and twelve questions; it does not
establish production accuracy. Recall@10 and semantic faithfulness are not invented.

The backend returns a completed research result rather than an event stream.
During a request the UI shows that it is running and actual elapsed waiting time.
Stop waiting aborts the browser request; it does not promise server cancellation.
There are no fabricated intermediate steps, token estimates or ingestion percentages.

Collections, multi-workspace switching, OCR, separate embedding-stage telemetry
and index disk size are unavailable. Saved research lacks per-channel candidate
scores; the inspector links to live Search Explorer for those. Provider LLM costs
exclude infrastructure costs. Monitoring counters reset when the process restarts.

## Verification and screenshots

- Backend: 45 tests passed, one optional service-integration test skipped.
- Ruff checks/format and mypy passed. Frontend: five metric tests, TypeScript and
  the Vite production build passed.
- All nine major views were visually reviewed at 1440×900, 1728×1117, 1920×1080
  and 1280×800: home, session, knowledge, search, experiments, evaluations,
  observability, document details and settings.
- Additional 390×844 phone checks cover all those views, upload and navigation.
  Research/evidence were checked at 1024×768. Page-level horizontal overflow was
  absent; wide experiment tables intentionally scroll internally on phones.
- Interaction checks cover a real filtered research query, citation/source matching,
  all inspector tabs, saved-session loading, live score retrieval, document chunks
  and metadata, experiment configuration/failures, actual run comparisons, live
  telemetry, command-menu keyboard handling, sidebar collapse and dialog dismissal.
- The revised upload dialog was reviewed responsively; ingestion itself is covered
  by the backend suite. A new end-to-end file upload was not repeated in this revision.

The screenshot matrix is in `docs/screenshots/qa/`; names begin with viewport width.
Wider screenshots use full-page capture and can be taller than the tested viewport.
The screenshots in `docs/screenshots/light-theme/` show the current white-and-blue theme. The earlier screenshot matrix records the 5 October layout validation.

The 6 October theme revision passed TypeScript and the Vite production build. Research home, a saved research session and loaded evaluations were visually checked; the QA tab reported no browser warnings or errors.
Docker deployment, broad cross-browser/device testing, load qualification and a
formal accessibility audit remain release gates; see [validation.md](validation.md).
