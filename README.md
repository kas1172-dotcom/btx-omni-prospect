# BTX Omni Prospect

BTX Omni Prospect is a governed commercial intelligence and prospecting platform
combining BTX commercial context, public market intelligence, deterministic
scoring and matching, geographic prospecting, and human-approved seller
workflows.

This repository contains the standalone proof of concept (POC). It is designed
to make commercial claims explainable: every meaningful result carries its
source, provenance, evidence state, or an explicit missing/unavailable state.

## POC surfaces

The current product posture is **POC mode · Real public market data with
simulated BTX commercial context**. The account universe contains only
researched public companies; curated scenarios are the default experience. See the [rich public scenario
matrix](docs/product/RICH_PUBLIC_SCENARIO_MATRIX.md) for field-level truth
rules, sources, and score-teaching scenarios.

- **Today** — prioritized intelligence, commercial alerts, and recommended work.
- **Accounts** — market accounts and Account 360 commercial context.
- **Intelligence** — resolved public signals with source lineage and relevance.
- **Map** — verified public locations, customer/target state, facilities, and proximity context.
- **Actions** — reviewable, assignable, human-approved seller workflows.
- **Omni** — a read-only conversational assistant with private saved conversations,
  bounded BTX lookups, optional public search and general questions.

## Core capabilities

- Canonical account identity, customer/target state, geography, facilities, and contact-research roles.
- Deterministic Account Attractiveness assessment with explicit simulated-input coverage.
- Paperless account and quote context, PRISM commercial context, and CRM ownership/deal/activity context.
- Evidence-linked intelligence, exact and structured commercial matching, and explicit ambiguity/conflict handling.
- Explainable commercial alerts and human-confirmed actions with audit and idempotency support.
- Governed Omni responses that are contextual and cited, never a source of record, and never autonomous CRM writes.

## Data modes and governance

`SAMPLE` describes only the BTX commercial context in this POC. Account identity,
contacts, locations, and intelligence use the researched public-company universe;
commercial, CRM, quote, workflow, and scoring selections remain simulated.

`CONNECTED` is intentionally not a fallback mode. It requires authorized,
configured source adapters; unavailable inputs remain unavailable rather than
being represented as sample or confirmed data. The governing capability contract
is in [the POC capability manifest](docs/product/POC_CAPABILITY_MANIFEST.md).

## Architecture

```text
apps/web (React/Vite)  ──►  backend (FastAPI)  ──►  PostgreSQL
                                  │
                       SAMPLE provider / governed contracts
                       scoring, alerts, intelligence, matching, work, Omni
```

The FastAPI application is organized by capability routers. The frontend uses
only those canonical API routes. PostgreSQL persists governed workflow and
decisioning state; the POC's SAMPLE provider supplies the shaped commercial
environment. See [architecture documentation](docs/architecture/) for repository
and GitHub setup guidance.

### Omni chat v2

The drawer uses `/api/omni/chat/stream`: a bounded model/tool loop, deterministic
read adapters, response validation, private audit and conversation storage. SSE
streams progress during tool use and answer paragraphs after validation, not raw
model tokens. The original `/api/omni` endpoint remains a legacy compatibility path.
Scores, eligibility, ranking and identity remain deterministic. Public search uses
Gemini Google Search grounding, never arbitrary URL fetching, and queries contain
only recorded public company names and approved topic phrases. Public findings are
not canonical evidence and cannot change prospects, scores or business records.

Omni cannot write CRM, Actions, communications or accepted memory. **Propose an
Action** opens the existing prefilled form for human review and saving. History,
feedback and audit receipts are private storage exceptions, not business evidence.
Conversations support resume, rename and deletion; deletion also removes their
feedback and linked answer receipts. Memory retains its separate acceptance controls.

| Setting | Default / meaning |
| --- | --- |
| `BTX_OMNI_CHAT_MODEL` | Unset: uses `BTX_GEMINI_MODEL` (currently `gemini-2.5-flash`) |
| `WEB_SEARCH_ENABLED` | true; also requires configured Gemini |
| `GENERAL_KNOWLEDGE_ENABLED` | true |
| `BTX_OMNI_CHAT_STEPS` | 6 read tools, maximum 12 |
| `BTX_OMNI_CHAT_OUTPUT_TOKENS` | 1200 per model response, maximum 4096 |
| `BTX_OMNI_CHAT_DAILY_CALLS` | 100 model calls per actor, subject to existing lower limits |
| `BTX_OMNI_CHAT_RETENTION_DAYS` | 30 inactivity days, maximum 365 |

Requests have a 60-second deadline, 8-second tool wait, 48,000-character turn-input
cap and one answer correction attempt. In-flight provider calls retain their
transport timeout; cancel stops further work and delivery. Without Gemini, Omni
says that only basic deterministic lookups are available. Search's closed vocabulary
and conservative factual checks can cause an explicit inability to answer; they do
not prove semantic correctness. Publication dates omitted by grounding stay unknown.

Private v2 storage includes server actor and tenant in ownership. Core commercial
data remains a single-workspace catalog. Hosted POC access codes map to shared
seller/manager identities: this is **not** individual-user production authentication
or proof of fully partitioned multi-tenancy.

Apply migration `0041_omni_conversations` to an authorized development database.
The normal backend `uv run pytest` command includes fake-provider chat evaluations.
From `backend`, run the optional live check with:

```powershell
uv run python scripts/omni_live_eval.py --output omni-live-eval.json
```

It skips cleanly if no Gemini key/configuration is present. Live execution uses
sample records, can incur provider usage, and writes a local report for human tone
and factual review; it never writes business data. See
[design and limitations](docs/product/OMNI_CHAT_V2_DESIGN.md) and
[validation report](docs/product/OMNI_CHAT_V2_REPORT.md) for what was actually tested.

## Engineering review

For a reviewer who is new to the project, start with the concise
[Engineering Review Guide](REVIEWER_GUIDE.md). It explains the actual POC
implementation, intentional boundaries, suggested reading order, and the
questions where architectural feedback is most valuable.

## Local development

Prerequisites:

- Python 3.11 and [uv](https://docs.astral.sh/uv/)
- Node 22.14.0 (see [`.nvmrc`](.nvmrc))
- Docker Desktop for local PostgreSQL

Start PostgreSQL from the repository root:

```powershell
docker compose -f infra/compose.yaml up -d
```

### Backend

```powershell
cd backend
Copy-Item .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn btx_omni.app:app --reload
```

The API health endpoint is `http://127.0.0.1:8000/api/health`; generated OpenAPI
is available at `http://127.0.0.1:8000/openapi.json`.

Backend configuration is always loaded from `backend/.env`, independent of the
startup working directory. Explicit process environment variables take precedence.

### Frontend

In a second shell:

```powershell
cd apps/web
Copy-Item .env.example .env
npm ci
npm run dev
```

`VITE_API_BASE_URL=/api` uses the local Vite proxy. Set it to the deployed
backend API base URL for a separately hosted frontend. `VITE_DATA_MODE=SAMPLE`
and `VITE_AUTH_MODE=development` describe the current POC contract.

## Tests and quality checks

Backend:

```powershell
cd backend
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run alembic current
```

Frontend:

```powershell
cd apps/web
npm run typecheck
npm run lint
npm test
npm run build
```

GitHub Actions runs these checks for pull requests and pushes to `main`, using
Python 3.11, PostgreSQL 16, and Node 22.14.0.

## Deployment

The backend has a production Dockerfile and [Fly.io configuration](fly.toml).
It runs migrations as a Fly release command and exposes `/api/health` for the
platform health check. Provide `DATABASE_URL` (or `BTX_DATABASE_URL`) and
`BTX_FRONTEND_ORIGINS` through the deployment environment; never commit secrets.

See [deferred connected dependencies](docs/deployment/DEFERRED_CONNECTED_DEPENDENCIES.md)
before enabling any connected mode integration.

## POC limitations and deferred integrations

- PRISM/PowerBI source fields and access require BTX confirmation.
- Paperless Parts production access and field mapping remain deferred.
- HubSpot production access and write conventions remain deferred.
- Okta/enterprise SSO is deferred; the POC uses development auth.
- Live public-source credentials/collectors are not wired.
- Overdue-order alerts remain unavailable until required order-level source fields are confirmed.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the small contribution workflow and
[SECURITY.md](SECURITY.md) for responsible vulnerability reporting.
