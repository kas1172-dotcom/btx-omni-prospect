from fastapi import FastAPI

from btx_omni.api.health import router as health_router
from btx_omni.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    app.include_router(health_router, prefix=settings.api_prefix)

    return app


app = create_app()