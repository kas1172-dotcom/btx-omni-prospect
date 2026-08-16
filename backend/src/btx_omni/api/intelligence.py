from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.intelligence.signals import normalize_signal

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("")
def intelligence(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    names = {item.legal_name: item.id for item in sample.accounts}
    accounts = {item.id: item for item in sample.accounts}
    signals = [normalize_signal(item, account_name_to_id=names, provenance=accounts[names[item.account_name]].provenance) for item in sample.intelligence_events]
    return {"signals": signals, "provenance": "source URL and evidence state are retained"}
