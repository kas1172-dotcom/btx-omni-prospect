from fastapi import APIRouter, Depends
from pydantic import BaseModel

from btx_omni.api.accounts import get_runtime
from btx_omni.api.actions import principal
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.work import Principal, PrincipalRole

router = APIRouter(prefix="/settings", tags=["settings"])


class PreferenceUpdate(BaseModel):
    compact_density: bool | None = None
    omni_evidence_expanded: bool | None = None


def _integration(state: str, detail: str) -> dict[str, str]:
    return {"state": state, "detail": detail}


@router.get("")
def settings(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    configured_gemini = bool(runtime.settings.gemini_api_key or (runtime.settings.gemini_mode == "vertex" and runtime.settings.google_cloud_project))
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
    }


@router.patch("/preferences")
def update_preferences(body: PreferenceUpdate, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    values = body.model_dump(exclude_none=True)
    return runtime.communication_repository.save_preferences(current.user_id, values, runtime.observed_at())
