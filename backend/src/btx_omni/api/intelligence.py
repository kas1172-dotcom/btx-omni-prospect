from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("")
def intelligence(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    signals = intelligence_signals(runtime)
    return {"signals": signals, "provenance": "source URL and evidence state are retained"}
