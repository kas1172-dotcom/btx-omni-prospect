## BTX Omni Prospect backend

Python 3.11 FastAPI service managed with `uv`.

```powershell
uv sync
uv run uvicorn btx_omni.app:app --reload
```

Copy `.env.example` to `.env` to override local settings. PostgreSQL is available
through `../infra/compose.yaml`.
