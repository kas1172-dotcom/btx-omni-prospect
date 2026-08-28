# Omni Prospect POC deployment

The backend target is Fly app `btx-omni-prospect` in `iad`. Its image is built with `backend/Dockerfile`; the production no-reload entrypoint is `uv run uvicorn btx_omni.app:app --host 0.0.0.0 --port 8080`. The Fly release command runs `uv run alembic upgrade head` before application start. The health endpoint is `/api/health`.

The frontend is the existing `apps/web` Vite build. A static host such as Vercel is the intended POC choice because it provides HTTPS, environment configuration, SPA fallback, and GitHub-based redeploys without another application. Set `VITE_API_BASE_URL` to the deployed Fly API origin plus `/api`.

## Map tiles

The current MapLibre runtime uses the public OpenStreetMap raster tile style directly and retains OpenStreetMap attribution. It does not consume `VITE_MAP_STYLE_URL` or `VITE_MAP_API_KEY`; no browser map-key configuration is required for the current POC map runtime. Do not represent a MapTiler configuration as active unless the map implementation is changed in a separately approved checkpoint.

## Runtime variables

Backend secrets are set in Fly, never committed: `DATABASE_URL`, an optional server-side `GEMINI_API_KEY`, `BTX_SAM_API_KEY` when SAM.gov is enabled, and `BTX_MONITOR_OPERATOR_TOKEN` for protected manual Monitor collection and governed Candidate promotion writes. Omni uses `BTX_AI_PROVIDER=gemini` and `BTX_GEMINI_MODEL`; Developer API mode uses the server key, while `BTX_GEMINI_MODE=vertex` uses the configured Google Cloud project/location and Application Default Credentials. No model credential belongs in frontend code. Gemini is independent from Google Maps, and unconfigured or unavailable model access leaves Omni in deterministic governed fallback mode. Promotion additionally requires explicit `confirmed: true`. Enterprise authentication remains deferred for this POC. If the configured durable database is unavailable, Monitor state must remain unavailable/degraded; it must not silently fall back to in-memory durable state.

Frontend public variables are `VITE_API_BASE_URL`, `VITE_DATA_MODE=SAMPLE`, and `VITE_AUTH_MODE=development`.

## Operations

Deploy backend with Fly after installing and authenticating `flyctl`; verify release migration, `/api/health`, `/openapi.json`, `/api/map`, and Monitor health. Deploy `apps/web` through the configured static host with the production API origin. Roll back backend by deploying a prior Fly image/release; do not downgrade database schema without an explicit migration plan.

Current posture is development auth, SAMPLE BTX internal context, and LIVE public intelligence. PRISM, Paperless, production HubSpot, and Okta/OIDC remain deferred.
