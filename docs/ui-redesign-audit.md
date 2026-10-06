# Research workspace audit and implementation plan

5 October 2026. Prepared before implementing the revised workspace brief.

## Current application

React 19, TypeScript, Vite and Lucide. Four views are selected by local React state:
Research, Knowledge library, Experiments and Observability. Navigation does not
currently update the URL. Nginx already supports SPA fallback and Vite proxies
`/api` to the existing FastAPI service.

The visual review covered the running research home, a successful question,
citations, agent timeline, library, experiments, observability and phone layout.
The preceding design has a large animated metallic hero, tiny metadata, abundant
sage-tinted text, and decorative serif headings. It is polished but allocates the
research home to presentation rather than work. This revised brief supersedes
that visual direction.

## Component audit

- **App.tsx:** combines server requests, session state, navigation, modals and all
  page markup. Split into hooks, layouts and feature components. Reuse typed
  request payloads, upload behavior, conversation persistence and citation IDs.
- **ResearchWelcome:** oversized introductory copy and sculpture conceal the
  useful workflow. Replace with compact composer, quick actions, recent sessions
  and actual knowledge statistics. Retire the decorative WebGL component.
- **Sidebar:** four destinations, fixed width, recent titles only. Replace the
  shell with a 248px collapsible navigation, seven stable destinations and a
  keyboard command layer. Preserve recent conversation identifiers.
- **Topbar:** no global command surface; Ctrl-K only focuses the composer. Replace
  that shortcut with a searchable command palette and real navigation actions.
- **Composer:** real `/chat` integration and document filtering already work.
  Extract and reuse them; add multiple-document selection, clearly mapped modes,
  active chips, multiline input and an honest stop-waiting control.
- **Research response:** real excerpts and source IDs are reliable; actions and
  advanced inspection are limited. Preserve answer text, add readable research
  typography, citation previews, copy/regenerate, verification and usage details.
- **Evidence sidebar:** two tabs and narrow content. Replace with collapsible
  Sources / Retrieval / Agent / Trace tabs at 380px. Reuse citations, query list,
  counts, provider identity, trace summaries, tokens and cost from responses.
- **Timeline dialog:** safe recorded actions exist, including elapsed duration
  and evidence IDs. Extract a shared AgentTimeline and measured TraceWaterfall.
  Do not treat the trace as private model reasoning or invent nested timings.
- **Knowledge library:** upload, status polling, document inspection and deletion
  work. Keep these contracts; add type filters, metadata and explicit chunk views.
- **Experiments:** `/evaluations` returns a real saved fixture. Reuse the JSON,
  display its actual Recall@5 (not Recall@10), and expose configurations and
  per-question outcomes through a second evaluations view.
- **Observability:** `/system` exposes real configuration and cache counters;
  `/metrics` exposes Prometheus aggregates. Retain them, add concise stage charts,
  sample-window request rate and persisted research trace inspection.
- **Dialogs and responsive code:** focus containment, Escape, source sheets and
  phone navigation exist. Move these into reusable accessible primitives and
  validate the requested desktop sizes plus a phone viewport.
- **CSS:** large monolithic styles and ad hoc tiny labels. Replace with semantic
  tokens and shared primitives, using neutral text and 12–16px content typography.

## API audit and truthful limits

Existing contracts to preserve: `/documents`, `/documents/upload`,
`/documents/{id}`, `/chat`, `/query`, `/conversations/{id}`, `/system`,
`/evaluations`, `/health`, `/ready` and `/metrics`; authentication remains the
existing session-scoped `X-API-Key` header.

SearchHit already contains actual dense, sparse, fusion and rerank scores inside
the retrieval engine. The current public response exposes only selected citation
scores. A small read-only `POST /search` adapter will expose the existing engine's
hits without generating an answer or changing retrieval logic. It will validate
filters/top-k and use the existing request deadline and error handling.

Add read-only `/conversations` summaries and `/evaluation-runs` plus
`/evaluation-runs/{run_id}` for existing stored conversations and allowlisted
benchmark files. Existing routes and response schemas remain unchanged. These
are presentation adapters, not an ML architecture redesign. Document and test the
new contracts before relying on them.

- No live agent-event stream or server cancellation endpoint exists. Show a real
  pending HTTP request and client elapsed time. Stop aborts waiting; it does not
  claim to terminate server work. Completed steps appear only after response.
- Ingestion reports queued, processing, ready or failed. Show these exact states,
  plus the client upload phase; never fabricate parsing/embedding percentages.
- Collections, index disk size, workspace switching and user accounts are not
  exposed. Hide unavailable actions or label the corresponding value Unavailable.
- Recorded evaluation metrics are document Recall@5, MRR, nDCG@5 and explicitly
  named lexical/exact-source proxies. Never relabel them as semantic faithfulness
  or answer correctness. Compare only stored runs and configurations.
- Prometheus percentile estimates must be labeled as histogram estimates.
  Request/min needs two observations; until then it is unavailable. Saved research
  requests are a scoped trace sample, not a complete distributed tracing service.

## Information architecture

`/research` (and `/`) — research home and session; session ID in the query string.
`/knowledge` — documents and chunk inspector.
`/search` — retrieval explorer using actual scored results.
`/experiments` — recorded runs, configurations, questions and failures.
`/evaluations` — measured retrieval/generation/latency comparison.
`/observability` — process metrics, recorded sessions, trace waterfall.
`/settings` — API connection, workspace capabilities and interface preferences.

## Design tokens

- Background `#0B0E0D`; navigation `#0E1210`; elevated `#121714`; card `#151B17`.
- Border `rgba(255,255,255,.07)`; selected border `rgba(167,215,181,.30)`.
- Text `#F3F5F3`; secondary `#A0AAA3`; subdued `#839087` for readable small copy.
- Accent `#A7D7B5`; success `#70C98B`; warning `#E7C778`; error `#E17B7B`.
- Sans-serif UI; IBM Plex Mono for IDs, scores, latency, counts and code.
- Titles 28–32px; sections 18px; body 14–16px; metadata 12–13px; labels 11px.
- Spacing 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48px.
- Sidebar 248px expanded / 68px collapsed; topbar 56px; inspector 380px.
- Borders and restrained 160ms transitions; no decorative hero or bright glow.

## Component map

`components/ui`: Button, IconButton, Badge, StatusBadge, Tabs, Dialog/Sheet,
Field, Select, Tooltip, Skeleton, EmptyState, ErrorState, Metric, Table and Toast.

`layouts`: AppShell and CommandPalette. `hooks`: routing, workspace server state,
research-session state and metrics sampling. `services`: typed API and benchmark
contracts; keep the current lightweight React state approach.

`components/research`: ResearchHome, ResearchComposer, ResearchResponse,
CitationPreview. `components/evidence`: EvidenceInspector and SourceSelector.
`components/agents`: AgentTimeline and TraceWaterfall. Lazy page modules for
Knowledge, Search, Experiments, Evaluations, Observability and Settings.

## Phased gates

1. Audit and plan: this document, source/API inspection and existing UI review.
2. Design system, application shell and Research Home. Build and visually inspect
   this first checkpoint before implementing the session redesign.
3. Research session, citations, four inspector tabs, trace and honest pending state.
4. Knowledge Base, uploads, document metadata and chunk inspection.
5. Search Explorer and its minimal scored-search adapter.
6. Experiment runs and evaluation comparisons based on recorded artifacts.
7. Observability and settings using actual service data.
8. Accessibility, responsive fixes, and screenshot review of every major page at
   1440×900, 1728×1117, 1920×1080 and 1280×800; phone sheet/navigation checks.
9. Final build, focused contract tests, documentation, refreshed screenshots and
   source archive. State any unexercised capabilities explicitly.
