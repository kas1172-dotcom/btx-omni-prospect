# Omni Prospect POC deployment

The backend target is Fly app `btx-omni-prospect` in `iad`. Its image is built with `backend/Dockerfile`; the Fly release command runs `uv run alembic upgrade head` before application start. The health endpoint is `/api/health`.

The frontend is the existing `apps/web` Vite build. A static host such as Vercel is the intended POC choice because it provides HTTPS, environment configuration, SPA fallback, and GitHub-based redeploys without another application. Set `VITE_API_BASE_URL` to the deployed Fly API origin plus `/api`.

## Map tiles

MapTiler is the production MapLibre style provider for the POC: it has a stable MapLibre-compatible style API, clear attribution, and a browser-key model. Set `VITE_MAP_API_KEY` to a domain-restricted public MapTiler key and set `VITE_MAP_STYLE_URL` to a MapTiler style URL containing that key. MapLibre attribution must remain visible. The map uses the environment style URL, so another MapLibre-compatible provider can be substituted without product code changes. Do not use demo tile endpoints in production.

## Runtime variables

Backend secrets are set in Fly, never committed: `DATABASE_URL`, `ANTHROPIC_API_KEY`, and `BTX_SAM_API_KEY` when SAM.gov is enabled. The backend environment also requires `BTX_FRONTEND_ORIGINS`, `BTX_MONITOR_MODE=live`, `BTX_AI_PROVIDER=anthropic`, and `BTX_ANTHROPIC_MODEL=claude-sonnet-5`.

Frontend public variables are `VITE_API_BASE_URL`, `VITE_DATA_MODE=SAMPLE`, `VITE_AUTH_MODE=development`, `VITE_MAP_STYLE_URL`, and `VITE_MAP_API_KEY`. Browser keys must be domain-restricted.

## Operations

Deploy backend with Fly after installing and authenticating `flyctl`; verify release migration, `/api/health`, `/openapi.json`, `/api/map`, and Monitor health. Deploy `apps/web` through the configured static host with the production API/map variables. Roll back backend by deploying a prior Fly image/release; do not downgrade database schema without an explicit migration plan.

Current posture is development auth, SAMPLE BTX internal context, and LIVE public intelligence. PRISM, Paperless, production HubSpot, and Okta/OIDC remain deferred.
