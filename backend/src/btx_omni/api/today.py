from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.monitor import monitor_health
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.command_center import build_command_center
from btx_omni.modules.federal_procurement import federal_today_candidates

router = APIRouter(prefix="/today", tags=["today"])


@router.get("")
def today(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    intelligence = intelligence_signals(runtime)
    observed_at = runtime.observed_at()
    alerts = CommercialAlertEngine().evaluate(
        sample.commercial_contexts,
        sample.quotes,
        orders=sample.orders,
        observed_at=observed_at,
    )
    monitor_snapshot = monitor_health(runtime)
    monitor_snapshot["watch_targets"] = runtime.monitor.watch_targets
    monitor_snapshot["source_markets"] = {
        source_id: adapter.definition.industries_supported
        for source_id, adapter in runtime.monitor.registry.items()
    }
    command_center = build_command_center(
        accounts=sample.accounts,
        programs=sample.programs,
        alerts=alerts,
        monitor_snapshot=monitor_snapshot,
        curated_signals=intelligence,
        generated_at=observed_at,
        public_as_of=datetime.now(UTC),
    )
    return {
        "data_mode": "SAMPLE",
        "priority_intelligence": intelligence,
        "commercial_alerts": alerts,
        "recommended_actions": [
            {
                "account_id": item.account_id,
                "action": item.recommended_action,
                "evidence_ids": item.evidence_ids,
            }
            for item in alerts
        ],
        "command_center": command_center,
        "federal_opportunities": federal_today_candidates(runtime),
    }
