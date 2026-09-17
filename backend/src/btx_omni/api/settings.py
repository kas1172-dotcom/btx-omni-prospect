from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.core.release import build_identity, database_compatibility
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.ai_usage import AiUsageRepository

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai-usage")
def ai_usage(response: Response, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        result = AiUsageRepository(runtime.work.repository.engine).summary(
            environment_id="btx-omni-prospect", actor_id=current.user_id, now=datetime.now(UTC))
    except SQLAlchemyError as error:
        raise HTTPException(503, "AI usage records are temporarily unavailable. No unmetered calls are permitted.") from error
    result['limits'] = {'workspace_daily_calls': runtime.settings.ai_daily_environment_calls,
                        'your_daily_calls': runtime.settings.ai_daily_actor_calls,
                        'workspace_concurrent_calls': runtime.settings.ai_concurrent_environment_calls,
                        'your_concurrent_calls': runtime.settings.ai_concurrent_actor_calls}
    return result


class PreferenceUpdate(BaseModel):
    compact_density: bool | None = None
    omni_evidence_expanded: bool | None = None


def _integration(state: str, detail: str) -> dict[str, str]:
    return {"state": state, "detail": detail}


@router.get("")
def settings(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    is_administrator = current.role is PrincipalRole.MANAGER
    configured_gemini = bool(runtime.settings.gemini_api_key or (runtime.settings.gemini_mode == "vertex" and runtime.settings.google_cloud_project))
    database = database_compatibility(runtime.work.repository.engine)
    identity = build_identity(runtime.settings)
    return {
        "principal": current,
        "preferences": runtime.communication_repository.preferences(current.user_id),
        "capabilities": {
            "create_communications": True,
            "review_communications": is_administrator,
            "manage_assignments": is_administrator,
            "configure_integrations": False,
            "view_source_health": is_administrator,
            "view_integration_diagnostics": is_administrator,
        },
        "integrations": {
            "google_maps": _integration("ADMIN_MANAGED", "Browser map configuration is deployment managed."),
            "gemini": _integration("CONFIGURED" if configured_gemini else "NOT_CONFIGURED", "Server-side Gemini with governed deterministic fallback."),
            "hubspot": _integration("ADMIN_MANAGED", "CRM adapter boundary; live write access is not enabled."),
            "communications": _integration("NOT_CONFIGURED", "Draft preview is available; external delivery is disabled."),
            "prism": _integration("SAMPLE", "Commercial context is SAMPLE in this environment; it is not a connected provider."),
            "sam_gov": _integration("NOT_CONFIGURED" if not runtime.settings.sam_api_key else "CONFIGURED", "Procurement source configuration is server managed."),
            "usaspending": _integration("CONNECTED" if runtime.settings.monitor_mode == "live" else "UNAVAILABLE", "Public procurement source availability follows the governed Monitor runtime."),
        },
        "release_diagnostics": ({
            "configuration_mode": runtime.settings.environment.upper(),
            "validation_state": "SCHEMA_COMPATIBLE_BUILD_DECLARED" if database['state'] == 'CURRENT' and identity['identity_state'] == 'DECLARED_CLEAN_BUILD' else "UNVERIFIED",
            "validation_scope": "Schema and build declaration only; not browser, provider or release acceptance.",
            "last_validated_at": database['checked_at'],
            "build": identity,
            "api": {"state": "AVAILABLE"},
            "database": database,
            "session": {
                "state": (
                    "SAMPLE_DEMO_AUTO_SESSION"
                    if runtime.settings.hosted_demo_access_bypass_enabled
                    else "DEVELOPMENT_ONLY"
                    if runtime.settings.environment == "development"
                    else "CONFIGURED"
                    if runtime.sessions.production_configured
                    else "NOT_CONFIGURED"
                ),
                "mode": (
                    "SAMPLE_DEMO_AUTO_SESSION"
                    if runtime.settings.hosted_demo_access_bypass_enabled
                    else "EXPLICIT_DEVELOPMENT_PRINCIPAL"
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
        } if is_administrator else None),
    }


@router.patch("/preferences")
def update_preferences(body: PreferenceUpdate, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    values = body.model_dump(exclude_none=True)
    return runtime.communication_repository.save_preferences(current.user_id, values, runtime.observed_at())
