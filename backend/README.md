## BTX Omni Prospect backend

Python 3.11 FastAPI service managed with `uv`.

```powershell
uv sync
uv run uvicorn btx_omni.app:app --reload
```

Copy `.env.example` to `backend/.env` to override local settings. That explicit
backend path is used whether Uvicorn starts from the repository root or from
`backend/`; process environment variables retain precedence. PostgreSQL is
available through `../infra/compose.yaml`.

Omni uses server-side Gemini when configured and otherwise remains available through
its deterministic governed fallback. Developer API-key and Google Cloud Vertex/ADC
configuration examples are documented in `.env.example`; no model credential belongs
in the web application. Google Maps uses a separate frontend integration and key.

An optional live provider check (never part of routine CI) can be run after configuring
Gemini with:

```powershell
uv run python -m btx_omni.ai.live_validation
```

## Hosted POC sessions

Production browser requests use an opaque, short-lived session held by the backend. `POST /api/session/sign-in` exchanges an administrator-issued server-side role access code for a secure HTTP-only cookie and CSRF token. The role access codes, cookie contents, Monitor operator token, and model credentials must remain deployment secrets and must never use a `VITE_*` variable.

For the canonical split deployment, configure `BTX_FRONTEND_ORIGINS=https://btx-omni-prospect.vercel.app`. The backend enables credentialed CORS for exact configured origins only; preview origins must be explicitly approved and listed. The cross-site Vercel-to-Fly cookie is `Secure`, `HttpOnly`, and `SameSite=None`, and every protected non-GET request requires `X-CSRF-Token`.

Development-only header principals remain available only when `BTX_ENVIRONMENT=development`. Production refuses the development tokens and has no implicit salesperson fallback. A durable corporate identity provider remains the required post-POC identity decision.

## Monitor worker

Monitor collection is an operator workload, never a browser control. With live
mode, durable state, a migrated PostgreSQL database, and applicable source
configuration enabled, one bounded cycle is:

```powershell
uv run python -m btx_omni.monitor.worker
```

An external Fly Scheduled Machine (or equivalent scheduler) should invoke that
command from the same release image and secret environment as the API. The
`BTX_MONITOR_WORKER_SOURCES`, `BTX_MONITOR_SOURCE_RECORD_LIMIT`,
`BTX_MONITOR_SOURCE_TARGET_LIMIT`, `BTX_MONITOR_WORKER_MAX_SECONDS`, and
`BTX_MONITOR_SOURCE_MIN_START_SECONDS` settings bound source collection. The
SAM/USAspending page sizes and request budgets bound each invocation without
discarding remaining work: per-query durable checkpoints continue unfinished
pages on the next scheduled run. SAM uses a posted-date overlap because its
public search API does not expose a documented modified-date filter. Set
`BTX_MONITOR_SAM_COLLECTION_MODE=backfill` for a controlled 365-day backfill;
return it to `incremental` after the backfill windows complete. The
deadline interrupts only the adapter/network phase; transactional persistence
finishes cleanly before exit. Source-version and event identities make repeat runs
idempotent, and a failed source does not erase successful source state.
After collection, the same locked worker may synthesize at most
`BTX_MONITOR_BRIEF_SYNTHESIS_CAP` eligible, previously unattempted governed
brief hashes. Results and safe failure statuses are durable; Monitor read/health
requests never invoke Gemini.
Successful hashes are reused indefinitely. Safe failure states carry an attempt
count and status-specific retry time; only a later worker cycle may retry them.
An unconfigured provider consumes no synthesis attempt and becomes eligible as
soon as server-side configuration is available.
Provisioning the scheduler remains a hosted-resource operation; application
startup does not create or authenticate scheduler resources.
Keep `BTX_MONITOR_SCHEDULE_CONFIGURED=false` until deployment explicitly
provisions the scheduler; worker readiness alone never claims an active schedule.
