# Omni Prospect POC deployment

The backend target is Fly app `btx-omni-prospect` in `iad`. Its image is built with `backend/Dockerfile`; the production no-reload entrypoint is `uv run uvicorn btx_omni.app:app --host 0.0.0.0 --port 8080`. The Fly release command runs `uv run alembic upgrade head` before application start. The health endpoint is `/api/health`.

The frontend is the existing `apps/web` Vite build. A static host such as Vercel is the intended POC choice because it provides HTTPS, environment configuration, SPA fallback, and GitHub-based redeploys without another application. Set `VITE_API_BASE_URL` to the deployed Fly API origin plus `/api`.

## Map tiles

MapTiler is the production MapLibre style provider for the POC: it has a stable MapLibre-compatible style API, clear attribution, and a browser-key model. Set `VITE_MAP_API_KEY` to a domain-restricted public MapTiler key and set `VITE_MAP_STYLE_URL` to a MapTiler style URL containing that key. MapLibre attribution must remain visible. The map uses the environment style URL, so another MapLibre-compatible provider can be substituted without product code changes. Do not use demo tile endpoints in production.

## Runtime variables

Backend secrets are set in Fly, never committed: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `BTX_SAM_API_KEY` when SAM.gov is enabled, and `BTX_MONITOR_OPERATOR_TOKEN` for protected manual Monitor collection and governed Candidate promotion writes. The backend environment also requires `BTX_FRONTEND_ORIGINS`, `BTX_MONITOR_MODE=live`, `BTX_MONITOR_DURABLE_STATE_ENABLED=true`, `BTX_AI_PROVIDER=anthropic`, and `BTX_ANTHROPIC_MODEL=claude-sonnet-5`. Promotion additionally requires explicit `confirmed: true`; neither confirmation nor the operator token belongs in frontend code. Enterprise authentication remains deferred for this POC. If the configured durable database is unavailable, Monitor state must remain unavailable/degraded; it must not silently fall back to in-memory durable state.

Frontend public variables are `VITE_API_BASE_URL`, `VITE_DATA_MODE=SAMPLE`, `VITE_AUTH_MODE=development`, `VITE_MAP_STYLE_URL`, and `VITE_MAP_API_KEY`. Browser keys must be domain-restricted.

## Operations

Deploy backend with Fly after installing and authenticating `flyctl`; verify release migration, `/api/health`, `/openapi.json`, `/api/map`, and Monitor health. Deploy `apps/web` through the configured static host with the production API/map variables. Roll back backend by deploying a prior Fly image/release; do not downgrade database schema without an explicit migration plan.

Current posture is development auth, SAMPLE BTX internal context, and LIVE public intelligence. PRISM, Paperless, production HubSpot, and Okta/OIDC remain deferred.
