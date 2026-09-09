from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from btx_omni.api.account_planning import router as account_planning_router
from btx_omni.api.accounts import router as accounts_router
from btx_omni.api.actions import router as actions_router
from btx_omni.api.commercial import router as commercial_router
from btx_omni.api.communications import router as communications_router
from btx_omni.api.federal_procurement import router as federal_procurement_router
from btx_omni.api.health import router as health_router
from btx_omni.api.intelligence import router as intelligence_router
from btx_omni.api.itineraries import router as itineraries_router
from btx_omni.api.map import router as map_router
from btx_omni.api.markets import router as markets_router
from btx_omni.api.monitor import router as monitor_router
from btx_omni.api.omni import router as omni_router
from btx_omni.api.omni_memory import router as omni_memory_router
from btx_omni.api.reference_fields import router as reference_fields_router
from btx_omni.api.relationships import router as relationships_router
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.api.session import router as session_router
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
        allow_origins=[
            origin.strip()
            for origin in settings.frontend_origins.split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["content-type", "x-btx-principal-token", "x-csrf-token"],
    )

    global runtime
    runtime = PocRuntime(settings)
    for router in (
        health_router,
        session_router,
        today_router,
        accounts_router,
        account_planning_router,
        reference_fields_router,
        commercial_router,
        relationships_router,
        intelligence_router,
        itineraries_router,
        federal_procurement_router,
        map_router,
        markets_router,
        actions_router,
        communications_router,
        settings_router,
        omni_router,
        omni_memory_router,
        monitor_router,
    ):
        # Enriched internal commercial projections are not public data. Keep only
        # health/session entry points and independently operator-authenticated
        # Monitor endpoints outside this principal boundary.
        dependencies = [] if router in (health_router, session_router, monitor_router) else [Depends(principal)]
        app.include_router(router, prefix=settings.api_prefix, dependencies=dependencies)

    @app.middleware("http")
    async def private_api_responses(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(settings.api_prefix + "/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    return app


runtime: PocRuntime
app = create_app()
