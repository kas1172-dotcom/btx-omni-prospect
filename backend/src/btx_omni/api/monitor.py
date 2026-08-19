import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.markets import primary_market_label
from btx_omni.monitor.sources import REGISTRY

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/sources")
def sources() -> list[dict]:
    return [{"source_id": item.definition.source_id, "source_name": item.definition.source_name, "source_tier": item.definition.source_tier, "industries_supported": item.definition.industries_supported, "event_types_supported": item.definition.event_types_supported, "cadence": item.definition.cadence, "authentication_requirement": item.definition.authentication_requirement} for item in REGISTRY.values()]


@router.get("/health")
def monitor_health(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    accounts = {item.id: item for item in runtime.environment().accounts}
    curated_preview = [
        {
            "id": signal["id"],
            "account_id": signal["account_id"],
            "company": accounts[signal["account_id"]].legal_name,
            "industry": primary_market_label(accounts[signal["account_id"]].industries),
            "event_type": signal["kind"],
            "title": signal["title"],
            "event_date": signal["observed_at"],
            "source_url": signal["source_url"],
            "evidence_state": signal["evidence_state"],
            "source_validation_state": signal.get("source_validation_state", "NEEDS_RESEARCH"),
            "data_mode": "CURATED_PUBLIC",
        }
        for signal in intelligence_signals(runtime)
        if signal.get("data_mode") == "CURATED_PUBLIC" and signal.get("account_id") in accounts
    ]
    durable = None
    try:
        durable = runtime.monitor.durable_snapshot()
    except SQLAlchemyError:  # database is intentionally optional until operational state is enabled
        durable = None
    if durable is None:
        sources_state = runtime.monitor.health
        last_runs = runtime.monitor.runs[-20:]
        events = tuple(runtime.monitor.events.values())
        rejected = tuple(runtime.monitor.rejected[-20:])
    else:
        health_by_source = {item["source_id"]: item for item in durable["health"]}
        now = datetime.now(UTC)
        sources_state = [
            {"source_id": source_id, **(health_by_source.get(source_id) or {"last_attempt_at": None, "last_success_at": None, "detail": "No durable collection run recorded."}), "state": runtime.monitor.source_state(source_id=source_id, last_success_at=(health_by_source.get(source_id) or {}).get("last_success_at"), now=now)}
            for source_id in REGISTRY
        ]
        last_runs, events, rejected = durable["runs"], durable["events"], durable["rejected"]
    collection_enabled = runtime.settings.monitor_mode.lower() == "live" and runtime.settings.monitor_durable_state_enabled
    return {
        "collection_enabled": collection_enabled,
        "durable_run_state": durable is not None,
        "seller_message": "Live ingestion is inactive: no scheduler or durable run state is configured." if not collection_enabled else "Operational collection is configured; seller UI cannot start collection.",
        "sources": sources_state,
        "last_runs": last_runs,
        "clusters": tuple(runtime.monitor.clusters.values()),
        "events": events,
        "rejected_observations": rejected,
        "curated_preview": curated_preview,
    }


@router.post("/collect/{source_id}")
def collect(source_id: str, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    # This POC intentionally has no public collector control plane.
    raise HTTPException(403, "Collection is disabled from the public POC UI. Use an authenticated operational worker when configured.")


@router.post("/internal/collect/{source_id}", include_in_schema=False)
def operational_collect(source_id: str, runtime: PocRuntime = Depends(get_runtime), operator_token: str | None = Header(default=None, alias="X-BTX-Monitor-Operator-Token")) -> dict:
    configured = runtime.settings.monitor_operator_token
    if not configured:
        raise HTTPException(503, "Operational collection is unavailable: BTX_MONITOR_OPERATOR_TOKEN is not configured.")
    if not operator_token or not hmac.compare_digest(operator_token, configured):
        raise HTTPException(403, "Operational collection authorization failed.")
    if not runtime.settings.monitor_durable_state_enabled:
        raise HTTPException(503, "Operational collection is unavailable: durable Monitor state is not enabled.")
    if source_id not in REGISTRY:
        raise HTTPException(404, "Unknown Monitor source.")
    run = runtime.monitor.collect(source_id)
    return {"run": run, "data_mode": "LIVE_PUBLIC" if not run.failures else "FAILED"}
