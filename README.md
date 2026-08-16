# BTX Omni Prospect

BTX Omni Prospect is a governed commercial intelligence and prospecting platform
combining BTX commercial context, public market intelligence, deterministic
scoring and matching, geographic prospecting, and human-approved seller
workflows.

This repository contains the standalone proof of concept (POC). It is designed
to make commercial claims explainable: every meaningful result carries its
source, provenance, evidence state, or an explicit missing/unavailable state.

## POC surfaces

- **Today** — prioritized intelligence, commercial alerts, and recommended work.
- **Accounts** — market accounts and Account 360 commercial context.
- **Intelligence** — resolved public signals with source lineage and relevance.
- **Map** — industry Top-100 layers, customer/target state, facilities, and proximity context.
- **Actions** — reviewable, assignable, human-approved seller workflows.
- **Omni** — a persistent, grounded assistant for the active commercial context.

## Core capabilities

- Canonical account identity, customer/target state, geography, facilities, and contact-research roles.
- Deterministic Account Attractiveness assessment, separate from external industry rank.
- Paperless account and quote context, PRISM commercial context, and CRM ownership/deal/activity context.
- Evidence-linked intelligence, exact and structured commercial matching, and explicit ambiguity/conflict handling.
- Explainable commercial alerts and human-confirmed actions with audit and idempotency support.
- Governed Omni responses that are contextual and cited, never a source of record, and never autonomous CRM writes.

## Data modes and governance

`SAMPLE` is the default POC mode. It uses the governed synthetic environment
described in [the scenario matrix](docs/migration/SAMPLE_SCENARIO_MATRIX.md),
including 600 market-universe accounts and 17 enriched scenario accounts.

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
