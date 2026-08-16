from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.intelligence.signals import normalize_signal

router = APIRouter(prefix="/today", tags=["today"])


@router.get("")
def today(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    accounts = {item.legal_name: item for item in sample.accounts}
    intelligence = [normalize_signal(item, account_name_to_id={name: account.id for name, account in accounts.items()}, provenance=accounts[item.account_name].provenance) for item in sample.intelligence_events]
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=runtime.observed_at())
    return {"data_mode": "SAMPLE", "priority_intelligence": intelligence, "commercial_alerts": alerts, "recommended_actions": [{"account_id": item.account_id, "action": item.recommended_action, "evidence_ids": item.evidence_ids} for item in alerts]}
