from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.monitor import monitor_health
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.command_center import build_command_center
from btx_omni.modules.federal_procurement import federal_today_candidates
from btx_omni.monitor.briefs import SignalBrief

router = APIRouter(prefix="/today", tags=["today"])


def _development_public_fixtures(now: datetime) -> tuple[SignalBrief, ...]:
    common = {
        "canonical_account_ids": ("boeing",),
        "canonical_program_id": None,
        "markets": ("Defense", "Commercial Aerospace"),
        "collection_timestamp": now,
        "freshness": "CURRENT",
        "source_url": "https://example.com/btx-today-development-fixture",
        "source_system": "development-fixture",
        "data_mode": "SAMPLE",
        "event_type": "CONTRACT_AWARD",
        "resolution_state": "RESOLVED",
        "seller_promotion_state": "RESOLVED_ELIGIBLE",
        "what_to_watch": "Review the source-supported date.",
        "missing_fields": (),
        "seller_summary": "Development-only governed public fixture.",
        "event_timing": "OBSERVED",
        "analysis_status": "READY",
        "commercial_relevance_state": "ESTABLISHED_COMMERCIAL_RELEVANCE",
        "priority_eligible": True,
    }
    return (
        SignalBrief(id="today-fixture-current", headline="Contract update reported", what_happened="A governed development fixture reported a current update.", why_it_may_matter="Review its explicit Customer context.", publication_timestamp=now - timedelta(hours=2), evidence_ids=("today-fixture-evidence",), recommended_action="Review the evidence.", **common),
        SignalBrief(id="today-fixture-upcoming", headline="Program update reported", what_happened="A governed development fixture reported an upcoming milestone.", why_it_may_matter="Review its explicit Customer context.", publication_timestamp=now - timedelta(hours=1), evidence_ids=("today-fixture-upcoming-evidence",), recommended_action="Review the upcoming milestone.", relevant_event_timestamp=now + timedelta(days=5), event_timing="UPCOMING", **{key: value for key, value in common.items() if key != "event_timing"}),
    )


def _development_public_fixtures_enabled(runtime: PocRuntime) -> bool:
    return (
        runtime.settings.today_public_fixture_mode
        and runtime.settings.environment.casefold() == "development"
    )


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
    if _development_public_fixtures_enabled(runtime):
        monitor_snapshot["signal_briefs"] = (
            *monitor_snapshot.get("signal_briefs", ()),
            *_development_public_fixtures(observed_at),
        )
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
