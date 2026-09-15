import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import ProviderStatus
from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.markets import primary_market_label
from btx_omni.monitor.briefs import (
    apply_cached_synthesis,
    brief_cache_id,
    governed_content_hash,
    signal_briefs_for_monitor,
)
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
        raise HTTPException(
            503,
            "Operational mutation is unavailable: BTX_MONITOR_OPERATOR_TOKEN is not configured.",
        )
    if not operator_token or not hmac.compare_digest(operator_token, configured):
        raise HTTPException(403, "Operational mutation authorization failed.")


def operator_runtime(
    runtime: PocRuntime = Depends(get_runtime),
    operator_token: str | None = Header(
        default=None, alias="X-BTX-Monitor-Operator-Token"
    ),
) -> PocRuntime:
    require_operator_token(runtime, operator_token)
    return runtime


@router.get("/candidates")
def monitor_candidates(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    """Read-only review contract for non-canonical Monitor identities."""
    if not runtime.monitor.repository:
        raise HTTPException(
            503, "Organization candidates require durable Monitor state."
        )
    organizations, programs = runtime.monitor.repository.candidates()
    return {
        "organization_candidates": jsonable_encoder(organizations),
        "program_candidates": jsonable_encoder(programs),
        "promotion_note": "Candidates are review-only. This endpoint does not create canonical Accounts or Programs.",
    }


@router.post("/candidates/{candidate_id}/promote")
def promote_candidate(
    candidate_id: str,
    request: CandidatePromotionRequest,
    runtime: PocRuntime = Depends(operator_runtime),
) -> dict:
    """An explicit POC operator action; this is never called by Monitor collection."""
    try:
        result = CandidatePromotionService().promote(
            runtime, candidate_id, confirmed=request.confirmed
        )
    except CandidatePromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "candidate": jsonable_encoder(result.candidate),
        "account": jsonable_encoder(result.account.account),
        "created": result.created,
        "confirmation_required": True,
    }


@router.post("/program-candidates/{candidate_id}/promote")
def promote_program_candidate(
    candidate_id: str,
    request: CandidatePromotionRequest,
    runtime: PocRuntime = Depends(operator_runtime),
) -> dict:
    """An explicit POC operator action; this is never called by Monitor collection."""
    try:
        result = ProgramCandidatePromotionService().promote(
            runtime, candidate_id, confirmed=request.confirmed
        )
    except ProgramCandidatePromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "candidate": jsonable_encoder(result.candidate),
        "program": jsonable_encoder(result.program.program),
        "created": result.created,
        "confirmation_required": True,
    }


@router.get("/sources")
def sources(runtime: PocRuntime = Depends(get_runtime)) -> list[dict]:
    return [
        {
            "source_id": item.definition.source_id,
            "source_name": item.definition.source_name,
            "source_tier": item.definition.source_tier,
            "industries_supported": item.definition.industries_supported,
            "event_types_supported": item.definition.event_types_supported,
            "cadence": item.definition.cadence,
            "authentication_requirement": item.definition.authentication_requirement,
            "content_structure": item.definition.content_structure,
            "freshness_threshold_hours": item.definition.freshness_threshold_hours,
            "seller_promotion_permitted": item.definition.seller_promotion_permitted,
            "targeting_mode": item.definition.targeting_mode if item.available(runtime.settings)[0] else "NOT_CONFIGURED",
            "consumes_strategic_targets": item.definition.consumes_strategic_targets,
        }
        for item in runtime.monitor.registry.values()
    ]


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
            "source_validation_state": signal.get(
                "source_validation_state", "NEEDS_RESEARCH"
            ),
            "data_mode": "CURATED_PUBLIC",
        }
        for signal in intelligence_signals(runtime)
        if signal.get("data_mode") == "CURATED_PUBLIC"
        and signal.get("account_id") in accounts
    ]
    durable = None
    try:
        durable = runtime.monitor.durable_snapshot()
    except (
        SQLAlchemyError
    ):  # database is intentionally optional until operational state is enabled
        durable = None
    if durable is None:
        sources_state = [
            runtime.monitor.operational_status(source_id) for source_id in REGISTRY
        ]
        last_runs = runtime.monitor.runs[-20:]
        events = tuple(runtime.monitor.events.values())
        rejected = tuple(runtime.monitor.rejected[-20:])
    else:
        health_by_source = {item["source_id"]: item for item in durable["health"]}
        now = datetime.now(UTC)
        last_runs, events, rejected = (
            durable["runs"],
            durable["events"],
            durable["rejected"],
        )
        runs_by_source = {item["source_id"]: item for item in reversed(last_runs)}
        sources_state = [
            runtime.monitor.operational_status(
                source_id,
                now=now,
                durable_health=health_by_source.get(source_id),
                last_run=runs_by_source.get(source_id),
            )
            for source_id in REGISTRY
        ]
    worker_ready = (
        runtime.settings.monitor_mode.lower() == "live"
        and runtime.settings.monitor_durable_state_enabled
    )
    latest_run = last_runs[0] if last_runs else None
    latest_completed = (
        latest_run.get("completed_at")
        if isinstance(latest_run, dict)
        else getattr(latest_run, "completed_at", None)
    )
    if latest_completed and latest_completed.tzinfo is None:
        latest_completed = latest_completed.replace(tzinfo=UTC)
    latest_failures = (
        latest_run.get("failures", ())
        if isinstance(latest_run, dict)
        else getattr(latest_run, "failures", ())
    )
    if not worker_ready:
        worker_runtime_state = "WORKER_RUNTIME_NOT_CONFIGURED"
        scheduler_state = "SCHEDULE_NOT_CONFIRMED"
    elif not runtime.settings.monitor_schedule_configured:
        worker_runtime_state = "WORKER_READY_FOR_INVOCATION"
        scheduler_state = "SCHEDULE_NOT_CONFIRMED"
    elif latest_run is None:
        worker_runtime_state = "WORKER_READY_FOR_INVOCATION"
        scheduler_state = "SCHEDULE_CONFIGURED_AWAITING_RUN"
    elif latest_failures:
        worker_runtime_state = "WORKER_READY_FOR_INVOCATION"
        scheduler_state = "LATEST_SCHEDULED_RUN_FAILED"
    elif latest_completed and datetime.now(UTC) - latest_completed > timedelta(hours=runtime.settings.monitor_stale_after_hours):
        worker_runtime_state = "WORKER_READY_FOR_INVOCATION"
        scheduler_state = "COLLECTION_OBSERVED_STALE"
    else:
        worker_runtime_state = "WORKER_READY_FOR_INVOCATION"
        scheduler_state = "COLLECTION_OBSERVED_CURRENT"
    collection_enabled = scheduler_state == "COLLECTION_OBSERVED_CURRENT"
    ai_config = AiConfig.from_settings(runtime.settings)
    provider_configured = bool(
        ai_config.api_key
        if ai_config.mode == "developer"
        else ai_config.project
    )
    synthesis_status = (
        ProviderStatus.UNAVAILABLE
        if provider_configured
        else ProviderStatus.NOT_CONFIGURED
    )
    briefs = []
    for deterministic in signal_briefs_for_monitor(runtime.monitor, environment=runtime.environment()):
        cached = (
            runtime.monitor.repository.brief_synthesis(
                brief_cache_id(deterministic), governed_content_hash(deterministic)
            )
            if runtime.monitor.repository
            else None
        )
        brief = apply_cached_synthesis(deterministic, cached)
        briefs.append(brief)
        if cached and cached.get("status") in ProviderStatus._value2member_map_:
            cached_status = ProviderStatus(cached["status"])
            if (
                cached_status is ProviderStatus.AVAILABLE
                or synthesis_status is ProviderStatus.UNAVAILABLE
            ):
                synthesis_status = cached_status
    return {
        "collection_enabled": collection_enabled,
        "worker_runtime_state": worker_runtime_state,
        "scheduler_state": scheduler_state,
        "brief_synthesis_status": synthesis_status,
        "durable_run_state": durable is not None,
        "seller_message": (
            "A recent scheduled collection is recorded; seller UI cannot start collection."
            if collection_enabled
            else (
                "Live ingestion is inactive. Monitor worker runtime is not configured, and no active schedule is verified."
                if worker_runtime_state == "WORKER_RUNTIME_NOT_CONFIGURED"
                else "Monitor worker readiness does not confirm an active schedule. No current scheduled collection is verified."
            )
        ),
        "sources": sources_state,
        "last_runs": last_runs,
        "clusters": tuple(runtime.monitor.clusters.values()),
        "events": events,
        "rejected_observations": rejected,
        "curated_preview": curated_preview,
        "signal_briefs": briefs,
    }


@router.post("/collect/{source_id}")
def collect(source_id: str, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    # This POC intentionally has no public collector control plane.
    raise HTTPException(
        403,
        "Collection is disabled from the public POC UI. Use an authenticated operational worker when configured.",
    )


@router.post("/internal/collect/{source_id}", include_in_schema=False)
def operational_collect(
    source_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    operator_token: str | None = Header(
        default=None, alias="X-BTX-Monitor-Operator-Token"
    ),
) -> dict:
    require_operator_token(runtime, operator_token)
    if not runtime.settings.monitor_durable_state_enabled:
        raise HTTPException(
            503,
            "Operational collection is unavailable: durable Monitor state is not enabled.",
        )
    if source_id not in REGISTRY:
        raise HTTPException(404, "Unknown Monitor source.")
    run = runtime.monitor.collect(source_id)
    return {"run": run, "data_mode": "LIVE_PUBLIC" if not run.failures else "FAILED"}


@router.post("/internal/collect", include_in_schema=False)
def operational_collect_all(
    runtime: PocRuntime = Depends(get_runtime),
    operator_token: str | None = Header(
        default=None, alias="X-BTX-Monitor-Operator-Token"
    ),
) -> dict:
    require_operator_token(runtime, operator_token)
    if not runtime.settings.monitor_durable_state_enabled:
        raise HTTPException(
            503,
            "Operational collection is unavailable: durable Monitor state is not enabled.",
        )
    runs = runtime.monitor.collect_all()
    return {
        "runs": runs,
        "data_mode": "LIVE_PUBLIC",
        "failed_sources": tuple(run.source_id for run in runs if run.failures),
    }
