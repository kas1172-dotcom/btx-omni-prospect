"""Projects canonical stored and live Monitor intelligence through one API contract."""

from __future__ import annotations

from fastapi.encoders import jsonable_encoder

from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.monitor.briefs import (
    apply_cached_synthesis,
    brief_cache_id,
    governed_content_hash,
    signal_briefs_for_monitor,
)
from btx_omni.monitor.service import current_event_contexts


def intelligence_signals(
    runtime: PocRuntime,
    *,
    account_ids: frozenset[str] | None = None,
    include_live: bool = True,
    live_limit: int = 50,
) -> list[dict]:
    sample = runtime.environment()
    names = {item.legal_name: item.id for item in sample.accounts}
    accounts = {item.id: item for item in sample.accounts}
    projected_briefs = []
    live_briefs = (
        signal_briefs_for_monitor(
            runtime.monitor,
            environment=sample,
            projection_limit=live_limit,
            account_ids=account_ids,
        )
        if include_live
        else ()
    )
    for deterministic in live_briefs:
        cached = (
            runtime.monitor.repository.brief_synthesis(
                brief_cache_id(deterministic), governed_content_hash(deterministic)
            )
            if runtime.monitor.repository
            else None
        )
        account_id = (
            deterministic.canonical_account_ids[0]
            if len(deterministic.canonical_account_ids) == 1
            else None
        )
        projected_briefs.append(apply_cached_synthesis(deterministic, cached))
    # Public-source membership is independent of replaced commercial scenarios.
    # An enriched ledger must not hide pre-existing public evidence for its account.
    curated_membership = {(item.id, item.account_id) for item in sample.public_signals}
    stored = [
        normalize_signal(
            item,
            account_name_to_id=names,
            provenance=accounts[names[item.account_name]].provenance,
        )
        for item in sample.intelligence_events
        if item.account_name in names
        and (item.source_id, names[item.account_name]) in curated_membership
        and (not account_ids or names[item.account_name] in account_ids)
    ]
    contexts = {
        event.id: (event, observation)
        for event, observation in current_event_contexts(runtime.monitor)
    }
    live: list[dict] = []
    for business in projected_briefs:
        event_context = contexts.get(business.id)
        if event_context is None or len(business.canonical_account_ids) != 1:
            continue
        event, _observation = event_context
        account_id = business.canonical_account_ids[0]
        if (
            event.seller_relevance_state.value
            not in {"RESOLVED_ELIGIBLE", "RESOLVED_NEEDS_REVIEW"}
            or event.resolution_state.value != "RESOLVED"
        ):
            continue
        live.append(
            {
                "id": event.id,
                "context_id": business.context_id,
                "kind": event.event_type.value,
                "title": business.headline,
                "source_url": business.source_url,
                "account_id": account_id,
                "program_name": event.program.mention,
                "program_id": event.program.canonical_program_id,
                "facility_id": event.canonical_facility_id,
                "evidence_state": event.provenance.evidence_state,
                "resolution_state": event.resolution_state,
                "data_mode": event.provenance.data_mode,
                "observed_at": business.publication_timestamp
                or event.event_date
                or event.provenance.observed_at,
                "relevance_explanation": business.why_it_may_matter,
                "business_briefing": jsonable_encoder(business),
                "evidence_ids": business.evidence_ids,
                "source_tier": event.source_confidence_basis,
                "provenance": event.provenance,
            }
        )
    return [
        *(
            {
                **jsonable_encoder(item),
                "observed_at": item.occurred_at,
                "data_mode": "CURATED_PUBLIC",
                "source_tier": "CURATED_POC_PUBLIC",
            }
            for item in stored
        ),
        *live,
    ]
