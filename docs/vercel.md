# Vercel deployment

## Service layout

The repository root contains `vercel.json` and `pyproject.toml`; the hosted API
entrypoint is `app/main.py`. The backend implementation remains in `src/atlasrag`
and the local/Docker entrypoint remains `apps/api/main.py`. The backend service
root is `.` so its shared source package and benchmark files are bundled, instead
of losing them by setting its service root to the entrypoint-only `app` directory.

The repository root contains `vercel.json`. Import the entire repository with
Vercel's project root set to `.`. Do not select `apps/web` as the project root or
set project-wide framework/build overrides: each service owns its build settings.

- `web`: static Vite frontend at `/`, including client routes and `/assets/*`.
- `app`: FastAPI service at `/api/*`, entrypoint `app.main:app`.
- Neither configured service is internal-only. API data routes still require the
  workspace key. Existing health/readiness/metrics exemptions are preserved under
  `/api`.

Vercel service routing preserves the original path. The deployment entrypoint
registers all API, operations and OpenAPI routes with `/api`; existing Docker and
plain Vite development use the unprefixed API entrypoint unchanged. Browser code
continues using same-origin `/api`, with no backend URL embedded in its bundle.

There are no service bindings because the frontend has no server functions: its
API requests originate in the browser, not a Vercel service function. `app` does
not call `web`. Runtime bindings cannot be read by static Vite browser code or
at build time. Do not create or manually set an unused API binding variable.
An optional `VITE_API_BASE_URL` changes the public browser API base; leave it
unset or set it to `/api` for this same-domain deployment. If using a separate
backend domain instead, include `/api` in that public URL and add the exact frontend
origin to `ATLAS_ALLOWED_ORIGINS`. Optional `VITE_GRAFANA_URL` controls the public
dashboard link; when unset, that link is hidden in production. These are public
build-time variables and require a frontend rebuild when changed.
`MRAG_DEV_API_URL` controls only the ordinary local Vite proxy.

If a server-side frontend or additional backend service is introduced later,
declare a four-field binding on that actual caller and consume it in the function.

## Required external infrastructure

This configuration deploys the two existing HTTP services. PostgreSQL, Redis and
Celery are external infrastructure, not localhost or Docker Compose containers
started by Vercel. A continuously running worker with Celery beat is required:

```sh
celery -A workers.tasks worker --beat --loglevel=INFO
```

Use the same MRAG code version, database and Redis on the worker. Its durable
job poller handles uploads and lease recovery; no HTTP service binding is needed
because the API and worker communicate through PostgreSQL and Redis. This worker
is not a third Vercel service in this configuration. Its host/provider
must be chosen before deployment. This two-service HTTP deployment does not
replace the existing Celery worker with a serverless background loop.

Set these environment variables securely in Vercel and on the external worker:

```dotenv
ATLAS_ENVIRONMENT=production
ATLAS_INGESTION_MODE=celery
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

Replace placeholders; do not commit credentials. Set the required variables for Production and Preview environments. The Vercel entrypoint explicitly
requires production settings and Celery ingestion and caps uploads at 3 MiB (or a smaller configured limit).
It will reject missing durable infrastructure or a missing workspace key rather
than start with ephemeral SQLite and a process-local background poller.
The API key is entered in the UI Settings and held in browser session storage;
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
migrations and start the external worker as described above. Enter the workspace
key privately in the MRAG Settings page after the API starts.

If the API returns `storage_not_ready`, verify the database connection and run
`alembic upgrade head`. If it returns `runtime_not_ready`, check Redis and any
configured model providers. Startup errors are sanitized; API readiness remains
unsuccessful until the service can actually initialize. Native local/Docker
startup behavior is unchanged.

The production project was inspected on 2026-10-06: Vercel showed **No Environment
Variables Added**, and `/api/health` returned HTTP 500 before these changes.
Provisioning production infrastructure is required in addition to deploying code.

## Local verification

Install the current Vercel CLI, `uv` (the Python builder uses `uv.lock`) and project dependencies, then configure the above
variables for a dedicated test database/Redis/worker and run from the repository root:

```sh
vercel dev -L
```

This starts the services together. Use `vercel dev` for a linked Vercel project.
There are no bindings in this layout; if added later, the CLI injects their URLs.
Verify `/research` refresh serves the SPA, `/assets/*` serves actual assets,
`/api/health` succeeds, `/api/ready` observes the worker heartbeat, unauthorized
`/api/system` is rejected, and authorized upload/poll/research/conversation paths
work. Check `/api/docs` and `/api/openapi.json` with authorization as well.

Local checks: 51 backend tests passed (one external integration test skipped), including prefixed paths, CORS, API-key authorization, production entrypoint
imports and monitoring label compatibility; Ruff and mypy passed, and the frontend production build passed.
Vercel CLI 62.4.0 recognized both services and started the Vite service. The Python wheel was built and its API was exercised outside the source checkout.
The configuration passed the official Vercel JSON schema. Full
`vercel dev -L` verification stopped because the local file watcher exceeded its open-file limit. The earlier
missing `uv` prerequisite was resolved using temporary validation tools. The CLI reached `app/main.py` successfully and then correctly rejected absent
production Redis configuration. The external test database, Redis and worker
still need to be configured before a live service test can pass.

No Vercel deployment, hosted build or external infrastructure has been verified
by adding this configuration. Provision the required infrastructure and variables before deploying a linked project.

References: [services routing](https://vercel.com/docs/services/routing),
[bindings](https://vercel.com/docs/services/bindings),
[FastAPI](https://vercel.com/docs/frameworks/backend/fastapi).

## Exact Vercel dashboard settings

1. Import `shyguy6479/MRAG`, selecting the branch with these changes.
2. Set **Root Directory** to `.` (the repository root).
3. Select the **Services** application preset. The service names are `app` and
   `web`; their framework presets are FastAPI and Vite respectively.
4. Use Node.js **22.x** for the web service. Python **3.12** is selected by
   `.python-version`. Retain `pyproject.toml`/`uv.lock` dependency detection.
5. Leave project-level Install/Build/Output overrides unset. `web` uses `npm ci`,
   `npm run build`, and `dist`, all relative to `apps/web`. `app` uses Python
   dependency installation and exports `app.main:app`; no uvicorn start command
   or Docker command is needed in Vercel's dashboard.
6. Add the required secure environment variables below, then apply migrations
   and run the external worker against the same production services. Use a
   separate database/Redis/worker configuration for Preview deployments.
7. Deploy; Vercel routes `/api/*` to FastAPI and other paths to Vite. Check
   `/api/ready`, then enter your workspace key in MRAG Settings and verify
   document upload, indexed status, search, citations and saved conversations.
8. Configure your final frontend origin in `ATLAS_ALLOWED_ORIGINS` if you want
   explicit CORS grants. When it is unset, the hosted entrypoint grants no
   cross-origin access; same-origin `/api` requests still work. Never use `*`.

Minimal secure variables to supply: `ATLAS_DATABASE_URL`, `ATLAS_REDIS_URL`,
`ATLAS_API_KEY`. The entrypoint selects production and Celery modes automatically.
Set `ATLAS_ENVIRONMENT=production` and `ATLAS_INGESTION_MODE=celery` on the external
worker too. `ATLAS_ALLOWED_ORIGINS` is a JSON array of exact origins, with no
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
