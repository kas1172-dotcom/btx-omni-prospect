from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from btx_omni.api.accounts import router as accounts_router
from btx_omni.api.actions import router as actions_router
from btx_omni.api.communications import router as communications_router
from btx_omni.api.health import router as health_router
from btx_omni.api.intelligence import router as intelligence_router
from btx_omni.api.map import router as map_router
from btx_omni.api.monitor import router as monitor_router
from btx_omni.api.omni import router as omni_router
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.settings import router as settings_router
from btx_omni.api.today import router as today_router
from btx_omni.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["content-type", "x-btx-principal-token"],
    )

    global runtime
    runtime = PocRuntime(settings)
    for router in (health_router, today_router, accounts_router, intelligence_router, map_router, actions_router, communications_router, settings_router, omni_router, monitor_router):
        app.include_router(router, prefix=settings.api_prefix)

    return app


runtime: PocRuntime
app = create_app()
