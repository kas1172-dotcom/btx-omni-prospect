## BTX Omni Prospect backend

Python 3.11 FastAPI service managed with `uv`.

```powershell
uv sync
uv run uvicorn btx_omni.app:app --reload
```

Copy `.env.example` to `.env` to override local settings. PostgreSQL is available
through `../infra/compose.yaml`.

Omni uses server-side Gemini when configured and otherwise remains available through
its deterministic governed fallback. Developer API-key and Google Cloud Vertex/ADC
configuration examples are documented in `.env.example`; no model credential belongs
in the web application. Google Maps uses a separate frontend integration and key.

An optional live provider check (never part of routine CI) can be run after configuring
Gemini with:

```powershell
uv run python -m btx_omni.ai.live_validation
```
