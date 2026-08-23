# BTX Omni Prospect — Engineering Review Guide

Thank you for reviewing this proof of concept. This is not a request for a line-by-line style review. The most useful feedback is about architecture, boundaries, data contracts, and the risks that would be expensive to discover after BTX connects real systems.

## What this product is

BTX Omni Prospect is a seller-facing commercial-intelligence workspace. It combines researched public market intelligence with **SAMPLE** BTX commercial context to help a seller identify accounts that need attention, understand why, and choose a reviewable next step.

The POC is deliberately honest about its limits:

- Public-company identity, locations, and intelligence are researched public data.
- BTX commercial, CRM, quote, workflow, and scoring inputs are simulated in `SAMPLE` mode.
- `CONNECTED` mode fails closed; it does not silently substitute SAMPLE data.
- No autonomous CRM writes are permitted.

## How it is actually built

```text
React 19 + TypeScript + Vite web app
              │ HTTP / typed API client
              ▼
FastAPI application (Python 3.11, Pydantic, capability routers)
              │
              ├─ framework-free domain models and governance primitives
              ├─ deterministic scoring, alerts, matching, intelligence, and work modules
              ├─ PostgreSQL 16 via SQLAlchemy Core + Alembic
              └─ SAMPLE / researched-public provider implementations
```

The web app never reaches the database or providers directly. The backend runtime is composed in [`backend/src/btx_omni/api/runtime.py`](backend/src/btx_omni/api/runtime.py).

**Omni note:** the current Omni request path is deterministic and composes responses from governed, typed context. An Anthropic provider adapter exists under `backend/src/btx_omni/ai/`, but it is not wired into Omni today.

## A quick review path

1. Read the root [`README.md`](README.md) for product framing and POC boundaries.
2. Read [`backend/src/btx_omni/api/runtime.py`](backend/src/btx_omni/api/runtime.py) to see what is constructed at startup.
3. Read [`backend/src/btx_omni/providers/contracts.py`](backend/src/btx_omni/providers/contracts.py) and the `providers/sample/` implementation to assess the SAMPLE → CONNECTED seam.
4. Read [`backend/src/btx_omni/modules/scoring/account_attractiveness.py`](backend/src/btx_omni/modules/scoring/account_attractiveness.py) and [`backend/src/btx_omni/modules/alerts/commercial.py`](backend/src/btx_omni/modules/alerts/commercial.py) for the deterministic commercial-logic pattern.
5. Read [`backend/src/btx_omni/modules/assistant/orchestration.py`](backend/src/btx_omni/modules/assistant/orchestration.py) with the Omni note above in mind; skim it before going deep.
6. Read [`apps/web/src/api/client.ts`](apps/web/src/api/client.ts) and one surface such as [`apps/web/src/features/accounts/Accounts.tsx`](apps/web/src/features/accounts/Accounts.tsx) to assess the frontend/API boundary.
7. Use the tests—especially [`backend/tests/test_poc_contracts.py`](backend/tests/test_poc_contracts.py)—to see the invariants the POC treats as load-bearing.

## What feedback would help most

1. Does the provider-contract / canonical-model seam look durable enough for real BTX schemas?
2. Is the separation between deterministic commercial logic and Omni sensible?
3. Where is the POC over-engineered or under-engineered for a connected pilot?
4. What would you change before adding real authentication, integrations, and enterprise data?
5. If you inherited this tomorrow, what are the three highest-leverage engineering priorities?

## What not to spend time on

- Formatting, naming nits, or small refactors unless they reveal a larger risk.
- Production-readiness gaps already intentionally deferred: live BTX integrations, enterprise SSO, production data classification approvals, and production deployment posture.
- Treating SAMPLE commercial context as a factual claim about BTX customers or relationships.

## Verification commands

From the repository root, start PostgreSQL with `docker compose -f infra/compose.yaml up -d`. Then run the backend checks in `backend/` (`uv run ruff check .`, `uv run pytest`, and `uv run alembic upgrade head`) and the frontend checks in `apps/web/` (`npm run typecheck`, `npm run lint`, `npm test`, and `npm run build`).
