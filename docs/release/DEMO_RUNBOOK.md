# Phase 1 Demo Runbook

This runbook produces the governed SAMPLE demonstration state. It never enables an external write.

1. Create an isolated PostgreSQL database, then set `BTX_DATABASE_URL` for that command/session only.
2. From `backend`, run `uv run alembic upgrade head`; verify `uv run alembic current` reports `0018_action_context_concurrency`.
3. Start the API: `uv run uvicorn btx_omni.app:app --host 127.0.0.1 --port 8000`.
4. From `apps/web`, run `npm ci` then `npm run dev`.
5. Use the server-side development Salesperson or Manager token only in a development/test environment. It is not production identity.

The runtime assembles the canonical SAMPLE projections; no separate seed command is required. Confirm `/api/health`, then use the following concise flow:

- **Seller:** Today → Intelligence → Customer 360 → Relationship Intelligence → create/review an internal Action → Omni follow-up. Omni may prepare a handoff but the seller explicitly saves the Action.
- **Federal:** Intelligence → Federal Procurement → Active Opportunities → Awarded Dollars. Explain source configuration and that Federal Opportunity Relevance is not PWin.
- **Manager:** use the Manager development context for supported Action assignment/approval/review; role authority remains server-side.

Do not describe SAMPLE commercial context as connected BTX data, or `NOT_CONFIGURED`/`UNAVAILABLE` providers as connected. A fresh database keeps any demo-created Actions isolated and disposable.
