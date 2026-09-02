# Phase 1 Release Candidate

**Candidate branch:** `phase-22-release-candidate`  
**Schema head:** `0018_action_context_concurrency`  
**Mode:** governed SAMPLE POC; it is not a live BTX commercial deployment.

## Reproduce a deterministic demo

1. Create an isolated PostgreSQL database and set `BTX_DATABASE_URL` only for the command/session.
2. From `backend`, run `uv run alembic upgrade head` and start `uv run uvicorn btx_omni.app:app --host 127.0.0.1 --port 8000`.
3. From `apps/web`, run `npm ci` then `npm run dev`.
4. Use the server-side development principal tokens for the Salesperson or Manager demonstration. They are test/development controls, not production identity.
5. Confirm `/api/health`, Today, Customers & Prospects, Intelligence, Federal Procurement, Map, Actions, Omni, and Settings load.

Canonical SAMPLE projections are assembled by the application runtime; no separate demo-data system is required. Use Boeing/Lockheed public intelligence and customer context, the Federal Procurement fixture views, governed Action workflow, and the built-in relationship/map projections. Demo-created Actions are isolated to the selected database.

## Provider and deployment truth

Commercial data is SAMPLE. HubSpot is an adapter boundary with no enabled live write. SAM.gov, Gemini, Map configuration, and Monitor sources are configuration-dependent; a missing configuration remains `NOT_CONFIGURED` or `UNAVAILABLE`. USAspending and curated public scenarios are not evidence of connected BTX commercial systems.

The repository has a production Docker entrypoint, Fly release migration command, health endpoint, CORS configuration, and provider abstraction. A BTX sandbox still needs BTX-managed Postgres, origins/secrets, production identity, approved provider credentials, and explicit source configuration. Do not deploy or enable external writes from this candidate.

## Known limitations

- Prism/BigQuery, Paperless, and live HubSpot access require BTX approval and configuration.
- Federal relevance is not PWin and needs BTX calibration.
- Relationships are deterministic bounded paths, not a weighted graph engine.
- Map output requires canonical supplied/verified facilities.
- Gemini is optional language assistance; governed fallback remains available.
