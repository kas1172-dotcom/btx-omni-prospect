from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.release import build_identity

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get('/build')
def build(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    """Public code identity only; no database, account, provider or session data."""
    return build_identity(runtime.settings)
