import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.markets import primary_market_label
from btx_omni.monitor.promotion import (
    CandidatePromotionError,
    CandidatePromotionService,
    ProgramCandidatePromotionError,
    ProgramCandidatePromotionService,
)
from btx_omni.monitor.sources import REGISTRY

router = APIRouter(prefix="/monitor", tags=["monitor"])


class CandidatePromotionRequest(BaseModel):
    confirmed: bool = False


def require_operator_token(runtime: PocRuntime, operator_token: str | None) -> None:
    """Guard durable operational writes; the token never enters browser state."""
    configured = runtime.settings.monitor_operator_token
    if not configured:
        raise HTTPException(503, "Operational mutation is unavailable: BTX_MONITOR_OPERATOR_TOKEN is not configured.")
    if not operator_token or not hmac.compare_digest(operator_token, configured):
        raise HTTPException(403, "Operational mutation authorization failed.")


def operator_runtime(
    runtime: PocRuntime = Depends(get_runtime),
    operator_token: str | None = Header(default=None, alias="X-BTX-Monitor-Operator-Token"),
) -> PocRuntime:
    require_operator_token(runtime, operator_token)
    return runtime


@router.get("/candidates")
def monitor_candidates(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    """Read-only review contract for non-canonical Monitor identities."""
    if not runtime.monitor.repository:
        raise HTTPException(503, "Organization candidates require durable Monitor state.")
    organizations, programs = runtime.monitor.repository.candidates()
    return {
        "organization_candidates": jsonable_encoder(organizations),
        "program_candidates": jsonable_encoder(programs),
        "promotion_note": "Candidates are review-only. This endpoint does not create canonical Accounts or Programs.",
    }


@router.post("/candidates/{candidate_id}/promote")
def promote_candidate(candidate_id: str, request: CandidatePromotionRequest, runtime: PocRuntime = Depends(operator_runtime)) -> dict:
    """An explicit POC operator action; this is never called by Monitor collection."""
    try:
        result = CandidatePromotionService().promote(runtime, candidate_id, confirmed=request.confirmed)
    except CandidatePromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "candidate": jsonable_encoder(result.candidate),
        "account": jsonable_encoder(result.account.account),
        "created": result.created,
        "confirmation_required": True,
    }


@router.post("/program-candidates/{candidate_id}/promote")
def promote_program_candidate(candidate_id: str, request: CandidatePromotionRequest, runtime: PocRuntime = Depends(operator_runtime)) -> dict:
    """An explicit POC operator action; this is never called by Monitor collection."""
    try:
        result = ProgramCandidatePromotionService().promote(runtime, candidate_id, confirmed=request.confirmed)
    except ProgramCandidatePromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "candidate": jsonable_encoder(result.candidate),
        "program": jsonable_encoder(result.program.program),
        "created": result.created,
        "confirmation_required": True,
    }


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
    require_operator_token(runtime, operator_token)
    if not runtime.settings.monitor_durable_state_enabled:
        raise HTTPException(503, "Operational collection is unavailable: durable Monitor state is not enabled.")
    if source_id not in REGISTRY:
        raise HTTPException(404, "Unknown Monitor source.")
    run = runtime.monitor.collect(source_id)
    return {"run": run, "data_mode": "LIVE_PUBLIC" if not run.failures else "FAILED"}


@router.post("/internal/collect", include_in_schema=False)
def operational_collect_all(runtime: PocRuntime = Depends(get_runtime), operator_token: str | None = Header(default=None, alias="X-BTX-Monitor-Operator-Token")) -> dict:
    require_operator_token(runtime, operator_token)
    if not runtime.settings.monitor_durable_state_enabled:
        raise HTTPException(503, "Operational collection is unavailable: durable Monitor state is not enabled.")
    runs = runtime.monitor.collect_all()
    return {"runs": runs, "data_mode": "LIVE_PUBLIC", "failed_sources": tuple(run.source_id for run in runs if run.failures)}
