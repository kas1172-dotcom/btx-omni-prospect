from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.alerts.commercial import CommercialAlertEngine

router = APIRouter(prefix="/today", tags=["today"])


@router.get("")
def today(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    intelligence = intelligence_signals(runtime)
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=runtime.observed_at())
    return {"data_mode": "SAMPLE", "priority_intelligence": intelligence, "commercial_alerts": alerts, "recommended_actions": [{"account_id": item.account_id, "action": item.recommended_action, "evidence_ids": item.evidence_ids} for item in alerts]}
