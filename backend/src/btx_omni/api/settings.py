from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.database import create_database_engine

router = APIRouter(prefix="/settings", tags=["settings"])


class PreferenceUpdate(BaseModel):
    compact_density: bool | None = None
    omni_evidence_expanded: bool | None = None


def _integration(state: str, detail: str) -> dict[str, str]:
    return {"state": state, "detail": detail}


@router.get("")
def settings(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    configured_gemini = bool(runtime.settings.gemini_api_key or (runtime.settings.gemini_mode == "vertex" and runtime.settings.google_cloud_project))
    engine = create_database_engine(runtime.settings)
    try:
        with engine.connect() as connection:
            migration_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    except SQLAlchemyError:
        migration_revision = None
    finally:
        engine.dispose()
    validated_at = runtime.observed_at()
    return {
        "principal": current,
        "preferences": runtime.communication_repository.preferences(current.user_id),
        "capabilities": {
            "create_communications": True,
            "review_communications": current.role is PrincipalRole.MANAGER,
            "manage_assignments": current.role is PrincipalRole.MANAGER,
            "configure_integrations": False,
        },
        "integrations": {
            "google_maps": _integration("ADMIN_MANAGED", "Browser map configuration is deployment managed."),
            "gemini": _integration("CONFIGURED" if configured_gemini else "NOT_CONFIGURED", "Server-side Gemini with governed deterministic fallback."),
            "hubspot": _integration("ADMIN_MANAGED", "CRM adapter boundary; live write access is not enabled."),
            "communications": _integration("NOT_CONFIGURED", "Draft preview is available; external delivery is disabled."),
            "prism": _integration("ADMIN_MANAGED", "SAMPLE commercial context in this environment."),
        },
        "release_diagnostics": {
            "configuration_mode": runtime.settings.environment.upper(),
            "validation_state": "VALID" if migration_revision else "DEGRADED",
            "last_validated_at": validated_at,
            "api": {"state": "AVAILABLE"},
            "database": {
                "state": "CURRENT" if migration_revision else "UNAVAILABLE",
                "migration_revision": migration_revision,
            },
            "session": {
                "state": (
                    "DEVELOPMENT_ONLY"
                    if runtime.settings.environment == "development"
                    else "CONFIGURED"
                    if runtime.sessions.production_configured
                    else "NOT_CONFIGURED"
                ),
                "mode": (
                    "EXPLICIT_DEVELOPMENT_PRINCIPAL"
                    if runtime.settings.environment == "development"
                    else "HOSTED_POC_SESSION"
                ),
            },
            "gemini": {"state": "CONFIGURED" if configured_gemini else "NOT_CONFIGURED"},
            "monitor": {
                "worker_state": "READY" if runtime.settings.monitor_mode == "live" else "DISABLED",
                "scheduler_state": "CONFIGURED" if runtime.settings.monitor_schedule_configured else "NOT_CONFIRMED",
            },
            "google_maps": {"state": "CLIENT_CONFIGURATION_ADMIN_MANAGED"},
            "connected_integrations": {"state": "NOT_CONFIGURED"},
        },
    }


@router.patch("/preferences")
def update_preferences(body: PreferenceUpdate, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    values = body.model_dump(exclude_none=True)
    return runtime.communication_repository.save_preferences(current.user_id, values, runtime.observed_at())
