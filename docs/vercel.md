# Vercel deployment

## Service layout

The repository root contains `vercel.json` and `pyproject.toml`; the hosted API
entrypoint is `app/main.py`. The backend implementation remains in `src/atlasrag`
and the local/Docker entrypoint remains `apps/api/main.py`. The backend service
root is `.` so its shared source package and benchmark files are bundled, instead
of losing them by setting its service root to the entrypoint-only `app` directory.

The `app` service's Vercel entrypoint must be **`pyproject.toml`**. The manifest
exports `app.main:app` and declares `workers.vercel_tasks:app` as a private queue
subscriber. A direct `app.main:app` service entrypoint deploys the API but skips
subscriber discovery in Services mode. That left uploads durably queued with
zero chunks. Verify the backend’s **two Python functions** in Deployment → Resources:
`/fastapi` and `/_py_subscribers/workers-vercel__tasks__app`.

The repository root contains `vercel.json`. Import the entire repository with
Vercel's project root set to `.`. Do not select `apps/web` as the project root or
set project-wide framework/build overrides: each service owns its build settings.

- `web`: public static Vite frontend at `/`, including client routes and `/assets/*`.
- `gateway`: public FastAPI gateway at `/api/*`, service root `gateway`, entrypoint
  `main.py`. Its own `requirements.txt` isolates its lightweight build.
- `app`: internal FastAPI backend, entrypoint manifest `pyproject.toml`.
- `gateway` binds to `app` through the runtime variable `MRAG_BACKEND_URL`.
  Vercel injects this value. Do not create it manually.

Every browser receives an isolated workspace through a signed, HttpOnly cookie.
Documents, conversations, job counts, retrieval snapshots and cache keys are
scoped on the server. Foreign document IDs cannot bypass this scope. The gateway reads the
existing server-only `ATLAS_API_KEY` and supplies it on internal backend requests.
Browser JavaScript neither receives nor sends that key; releases remove the legacy
browser session copy. Settings contains private workspace details and shortcuts, with no
connection form or connection status indicators. The backend retains API-key
validation. Public traffic has no rewrite directly to `app` or its worker.
The gateway allowlists workspace routes, preserves upload bytes and API statuses,
bounds request bodies, blocks cross-origin browser writes, and prevents response
caching. The existing Redis rate and corpus limits remain in effect. This is a
private browser workspace, including upload, retry and document deletion.
It provides device/browser isolation, not an account system or cross-device sync.
Clearing cookies or rotating the signing key starts a new workspace.

Vercel service routing preserves `/api` on both gateway and backend calls.
The binding URL is used only in a server function, never a static build or middleware.
`VITE_API_BASE_URL` should be unset or `/api`. Never put credentials in `VITE_*`.
Optional `VITE_GRAFANA_URL` controls the public dashboard link.
`MRAG_DEV_API_URL` controls the ordinary local Vite proxy; local Vite injects the
gateway URL (default `http://127.0.0.1:8001`). Start the local gateway with
`uvicorn gateway.main:app --host 127.0.0.1 --port 8001`; it forwards to the local
API at port 8000. Both servers read server-only `ATLAS_API_KEY` when configured.

## Required external infrastructure

This configuration deploys three HTTP services and one private queue subscriber.
PostgreSQL and Redis are managed services, not localhost or Docker containers.
Use Neon Free for PostgreSQL and Upstash Free for Redis. Connect integrations to
Production only with the `ATLAS` variable prefix. Standard `postgresql://` URLs
from Neon are normalized to the project's declared psycopg driver automatically.

Vercel's hosted entrypoint selects `ingestion_mode=vercel`. The Celery subscriber
`workers.vercel_tasks:app` uses Vercel Queues and runs only when a job arrives;
it requires no separate always-on worker host. Uploads are committed to PostgreSQL
before notifying the queue. Each invocation processes one leased job and wakes
the next. Active document polling recovers jobs if publishing failed, throttled
to once per 30 seconds through Redis. If no browser is polling after a publish
failure, that job waits for the next document-list request. Late acknowledgments
allow Vercel to redeliver interrupted tasks after their queue lease expires.
No public rewrite or HTTP service binding is needed for the private subscriber.
Redis remains required for shared caching and rate limits.

Transient indexing failures retain the PostgreSQL job and schedule a durable
retry after 5 then 10 seconds, with three processing attempts per admission.
The worker schedules the next wake-up through Vercel Queues, including recovery
of expired database leases, without requiring an open browser. No request-local
background task runs ingestion. The database lease outlives the hosted function
limit so interrupted deliveries cannot overlap active indexing.

**Retry processing** in Knowledge Base or document details calls authenticated
`POST /api/documents/{id}/retry`. It reuses the stored upload and resets exhausted
attempts. Active worker leases and already indexed documents return HTTP 409;
deleted/missing documents return 404. Chunk replacement, Indexed state, job
completion and corpus revision are committed atomically after extraction and
any configured vector write. Failed documents never enter retrieval snapshots.

Stage logs include document/job IDs, attempt number, extracted sections, chunk
counts, publication and elapsed time. Errors expose the failing stage and safe
classification in the document UI; provider credentials and raw exception bodies
are never returned. The baseline uses PostgreSQL chunks with BM25 and TF-IDF/SVD
indexes rebuilt per corpus revision; it does not require an external embedding
API or Qdrant. When neural/Qdrant is configured, vector upsert must succeed before
the document is published.

The Vercel Celery adapter is an explicit, locked dependency, with static imports
in both hosted entrypoints. This keeps it in each function's dependency bundle;
relying on the builder's automatic installation alone caused a runtime
`ModuleNotFoundError: No module named 'vercel'` before the API could start.

The existing Docker deployment still uses `ingestion_mode=celery` with its
separate worker and scheduler. For a traditional worker outside Vercel, use:

```sh
celery -A workers.tasks worker --beat --loglevel=INFO
```

Set these environment variables securely in Vercel:

```dotenv
ATLAS_ENVIRONMENT=production
ATLAS_INGESTION_MODE=vercel
ATLAS_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require
ATLAS_REDIS_URL=rediss://USER:PASSWORD@HOST:PORT/0
ATLAS_API_KEY=YOUR_RANDOM_KEY_OF_AT_LEAST_32_CHARACTERS
ATLAS_ALLOWED_ORIGINS=["https://YOUR_DEPLOYMENT_DOMAIN"]
ATLAS_DENSE_BACKEND=lsa
ATLAS_VECTOR_BACKEND=memory
ATLAS_RERANKER=lexical
ATLAS_GENERATOR=extractive
ATLAS_MAX_UPLOAD_BYTES=3145728
```

Replace placeholders; do not commit credentials. Configure Production first;
only enable Preview deployments with their own isolated infrastructure and keys.
The Vercel entrypoint explicitly
requires production settings and queue ingestion and caps uploads at 3 MiB (or a smaller configured limit).
It will reject missing durable infrastructure or a missing workspace key rather
than start with ephemeral SQLite and a process-local background poller.
The API key remains in the gateway and backend server environments;
it must never be supplied as a `VITE_*` build variable.

Run `alembic upgrade head` from a trusted environment with the database settings
before release. Stored documents, chunks and conversations live in PostgreSQL;
the in-memory retrieval index is rebuilt on demand from that durable corpus.
Process-local monitoring resets with function instances and is not a fleet-wide
metric. The recorded benchmark artifacts are bundled repository files.

The hosted deployment defaults to the lightweight extractive profile. To use
chat generation, set `ATLAS_GENERATOR=chat`, a reachable HTTPS
`ATLAS_LLM_BASE_URL`, `ATLAS_LLM_MODEL`, `ATLAS_LLM_KEY` and actual token prices.
Do not use `localhost:11434` on Vercel. A neural deployment needs the neural extra,
pinned model revisions, accessible models and a separately qualified bundle size
and cold-start budget. Qdrant, if enabled, needs a managed `ATLAS_QDRANT_URL`,
credentials and neural embeddings; `http://qdrant:6333` is Docker-only.

## Troubleshooting a disconnected workspace

The frontend can deploy successfully while the FastAPI service fails at startup.
Vercel runtime logs also identified `ModuleNotFoundError: No module named
'atlasrag'`: the dependency environment did not expose the repository's `src`
package. The API function now explicitly bundles `src/atlasrag/**`, and its
entrypoint resolves `src` relative to its own file before importing the backend.
An isolated entrypoint test verifies this without an installed project package.
Check `/api/health` before investigating browser CORS. Missing production settings
previously caused `FUNCTION_INVOCATION_FAILED`; the hosted entrypoint now returns
HTTP 503 with `deployment_not_configured` and missing variable **names**. It never
returns secret values or reports a healthy service when setup is incomplete.

In **Settings → Environment Variables**, configure `ATLAS_DATABASE_URL`,
`ATLAS_REDIS_URL` and `ATLAS_API_KEY` for Production, then redeploy. Use hosted
PostgreSQL and Redis URLs, not Docker service names or localhost. Run the database
migrations and deploy the private queue subscriber described above. Enter the workspace
key in Vercel server environments; visitors do not enter a key.

If the API returns `storage_not_ready`, verify the database connection and run
`alembic upgrade head`. If it returns `runtime_not_ready`, check Redis and any
configured model providers. Startup errors are sanitized; API readiness remains
unsuccessful until the service can actually initialize. Native local/Docker
startup behavior is unchanged.

The original deployment had no production environment variables and returned
HTTP 500. The source import and Celery adapter bundling fixes now let the API
start and return a sanitized HTTP 503 diagnostic when configuration is missing.
The frontend reports the same error once, without duplicate banners. Configure
the remaining settings and redeploy before expecting a connected workspace.

## Local verification

Install the current Vercel CLI, `uv` (the Python builder uses `uv.lock`) and project dependencies, then configure the above
variables for a dedicated test database/Redis/worker and run from the repository root:

```sh
vercel dev -L
```

This starts the services together. Use `vercel dev` for a linked Vercel project.
The CLI injects `MRAG_BACKEND_URL` for the gateway-to-app binding.
Verify `/research` refresh serves the SPA, `/assets/*` serves actual assets,
`/api/health` succeeds, `/api/ready` checks PostgreSQL and Redis, unauthorized
`/api/system` is rejected, and authorized upload/poll/research/conversation paths
work. Check `/api/docs` and `/api/openapi.json` with authorization as well.

Local checks: 63 backend tests passed (one external integration test skipped), including prefixed paths, CORS, API-key authorization, production entrypoint
imports and monitoring label compatibility; Ruff and mypy passed, and the frontend production build passed.
Vercel CLI 62.4.0 recognized both services and started the Vite service. The Python wheel was built and its API was exercised outside the source checkout.
The configuration passed the official Vercel JSON schema. Full
`vercel dev -L` verification stopped because the local file watcher exceeded its open-file limit. The earlier
missing `uv` prerequisite was resolved using temporary validation tools. The CLI reached `app/main.py` successfully and then correctly rejected absent
production Redis configuration. Hosted ingestion and research were subsequently
verified against the configured Production project.

On 2026-10-11, Neon Free was connected to Production and migration `0001` was
applied and verified. On 2026-10-12, Upstash Redis Free (`mrag-redis`, region
`iad1`) was provisioned and connected to Production only with the `ATLAS` prefix.
The integration supplies `ATLAS_REDIS_URL`; its REST URL and tokens are not
substitutes for this Redis connection URL. Credentials remain in Vercel.
The owner saved the private `ATLAS_API_KEY` and Production is authenticated.
On 2026-10-12, fixing the service entrypoint to `pyproject.toml` deployed the
previously missing private queue subscriber. The original stored PDF was processed
without a new upload: **54 indexed chunks across 27 page sections**. Live Search
returned page-preserving MLOps passages and Research returned cited GenAI evidence.
PDF table line wrapping is preserved during context selection and extractive
answering; source excerpts still pass exact-text grounding verification.

References: [services routing](https://vercel.com/docs/services/routing),
[bindings](https://vercel.com/docs/services/bindings),
[FastAPI](https://vercel.com/docs/frameworks/backend/fastapi).

## Exact Vercel dashboard settings

1. Import `shyguy6479/MRAG`, selecting the branch with these changes.
2. Set **Root Directory** to `.` (the repository root).
3. Select the **Services** application preset. The service names are `app`, `gateway` and
   `web`; their framework presets are FastAPI, FastAPI and Vite respectively.
4. Use Node.js **22.x** for the web service. Python **3.12** is selected by
   `.python-version`. Retain `pyproject.toml`/`uv.lock` dependency detection.
5. Leave project-level Install/Build/Output overrides unset. `web` uses `npm ci`,
   `npm run build`, and `dist`, all relative to `apps/web`. `app` uses Python
   dependency installation and exports `app.main:app`; no uvicorn start command
   or Docker command is needed in Vercel's dashboard.
6. Add the required secure environment variables below, then apply migrations
   and deploy the private queue subscriber against the same production services. Use a
   separate database/Redis/worker configuration for Preview deployments.
7. Deploy; Vercel routes `/api/*` to FastAPI and other paths to Vite. Check
   `/api/ready`, then verify isolated browser-workspace access and
   document upload, indexed status, search, citations and saved conversations.
8. Configure your final frontend origin in `ATLAS_ALLOWED_ORIGINS` if you want
   explicit CORS grants. When it is unset, the hosted entrypoint grants no
   cross-origin access; same-origin `/api` requests still work. Never use `*`.

Minimal secure variables to supply: `ATLAS_DATABASE_URL`, `ATLAS_REDIS_URL`,
`ATLAS_API_KEY`. The entrypoint selects production and Vercel queue modes automatically.
`ATLAS_ALLOWED_ORIGINS` is a JSON array of exact origins, with no
trailing slash or path, such as `["https://mrag.example.com"]`.

The recommended baseline profile variables in the earlier dotenv block avoid
model downloads; only add the chat/neural variables if using those capabilities.
Neither `VITE_API_BASE_URL` nor `VITE_GRAFANA_URL` is mandatory. Never set
`VITE_API_KEY`, `VITE_LLM_KEY`, or any other secret-bearing `VITE_*` variable.

## Complete environment variable inventory

All backend settings use the `ATLAS_` prefix. The following names are exhaustive
for `Settings`; unset optional values use its validated defaults. This is an
inventory, not a requirement to enter every variable in Vercel.

- `ATLAS_ENVIRONMENT`
- `ATLAS_DATABASE_URL`
- `ATLAS_REDIS_URL`
- `ATLAS_API_KEY`
- `ATLAS_ALLOWED_ORIGINS`
- `ATLAS_INGESTION_MODE`
- `ATLAS_DENSE_BACKEND`
- `ATLAS_VECTOR_BACKEND`
- `ATLAS_EMBEDDING_MODEL`
- `ATLAS_EMBEDDING_REVISION`
- `ATLAS_QDRANT_URL`
- `ATLAS_QDRANT_KEY`
- `ATLAS_QDRANT_COLLECTION`
- `ATLAS_RERANKER`
- `ATLAS_RERANKER_MODEL`
- `ATLAS_RERANKER_REVISION`
- `ATLAS_GENERATOR`
- `ATLAS_LLM_BASE_URL`
- `ATLAS_LLM_MODEL`
- `ATLAS_LLM_KEY`
- `ATLAS_LLM_FREE_INFERENCE`
- `ATLAS_INPUT_COST_PER_MILLION`
- `ATLAS_OUTPUT_COST_PER_MILLION`
- `ATLAS_DENSE_TOP_K`
- `ATLAS_SPARSE_TOP_K`
- `ATLAS_FINAL_TOP_K`
- `ATLAS_RRF_K`
- `ATLAS_CHUNK_SIZE`
- `ATLAS_CHUNK_OVERLAP`
- `ATLAS_CONTEXT_TOKENS`
- `ATLAS_MAX_UPLOAD_BYTES`
- `ATLAS_MAX_DOCUMENTS`
- `ATLAS_MAX_CHUNKS`
- `ATLAS_MAX_AGENT_STEPS`
- `ATLAS_QUERY_TIMEOUT_SECONDS`
- `ATLAS_MAX_QUERY_TOKENS`
- `ATLAS_MAX_OUTPUT_TOKENS`
- `ATLAS_MAX_QUERY_COST`
- `ATLAS_PROVIDER_TIMEOUT_SECONDS`
- `ATLAS_PROVIDER_RETRIES`
- `ATLAS_CACHE_TTL_SECONDS`
- `ATLAS_CACHE_MAX_ENTRIES`
- `ATLAS_RATE_LIMIT_PER_MINUTE`
- `ATLAS_GROUNDING_THRESHOLD`
- `ATLAS_OTLP_ENDPOINT`
- `ATLAS_LOG_LEVEL`

Frontend configuration: `VITE_API_BASE_URL`, `VITE_GRAFANA_URL`.
Local Vite development only: `MRAG_DEV_API_URL`.
`POSTGRES_PASSWORD` and `GRAFANA_PASSWORD` configure the Docker Compose stack;
`ATLAS_INTEGRATION_DATABASE_URL` and `ATLAS_INTEGRATION_REDIS_URL` are integration
test inputs. They are not Vercel application settings. `PORT`, `VERCEL` and related
platform variables are owned by Vercel; do not create internal binding URL values.

## Private-workspace gateway verification

The service `gateway` receives `/api/:path*`; `web` receives the final catch-all.
`app` has no public rewrite. The four-field binding is declared on `gateway`:
`type=service`, `service=app`, `format=url`, `env=MRAG_BACKEND_URL`.
Keep the existing `ATLAS_API_KEY` available to both Python services in Production;
no new manually entered secret is required. The private ingestion subscriber stays
on `app` and continues using PostgreSQL and Vercel Queues unchanged.
Tests verify two browser identities cannot access each other’s documents,
conversations, job counts or cached retrieval results. Direct backend access
without the server key remains unauthorized.

References: [Vercel service bindings](https://vercel.com/docs/services/bindings) and
[service routing](https://vercel.com/docs/services/routing).

## Workspace isolation release (0002)

Migration `0002` adds indexed `workspace_id` columns to documents and messages.
The hosted API and worker apply only this additive migration from `0001` inside a
transaction, protected by a PostgreSQL advisory lock. Unknown schema versions fail
closed. Operators can also run `alembic upgrade head` before deployment.
Existing shared rows are preserved under `legacy`, inaccessible to new visitor
workspaces. An operator can assign those rows to the verified owner’s workspace
reference using the database console; no public claim endpoint exists.
The reference is an identifier, not a credential. The signed cookie is HttpOnly,
Secure in Vercel, SameSite=Strict, and expires after one year. `/api/workspace`
bootstraps it once before other client requests; arbitrary tenant headers and
forged cookies cannot select another workspace. The API key stays server-only.
