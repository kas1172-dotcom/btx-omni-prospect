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


def intelligence_signals(runtime: PocRuntime) -> list[dict]:
    sample = runtime.environment()
    names = {item.legal_name: item.id for item in sample.accounts}
    accounts = {item.id: item for item in sample.accounts}
    business_briefs = {}
    for deterministic in signal_briefs_for_monitor(runtime.monitor, environment=sample):
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
        business_briefs[(deterministic.id, account_id)] = apply_cached_synthesis(
            deterministic, cached
        )
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
    ]
    live: list[dict] = []
    for event, observation in current_event_contexts(runtime.monitor):
        subjects = tuple(
            item for item in event.subject_entities if item.canonical_account_id
        )
        if (
            event.seller_relevance_state.value
            not in {"RESOLVED_ELIGIBLE", "RESOLVED_NEEDS_REVIEW"}
            or event.resolution_state.value != "RESOLVED"
            or not subjects
        ):
            continue
        for subject in subjects:
            business = business_briefs.get((event.id, subject.canonical_account_id))
            live.append(
                {
                    "id": event.id,
                    "context_id": business.context_id
                    if business
                    else f"{event.id}:{subject.canonical_account_id}",
                    "kind": event.event_type.value,
                    "title": next(
                        (
                            claim.value
                            for claim in event.claims
                            if claim.predicate == "source_title"
                        ),
                        event.event_type.value,
                    ),
                    "source_url": observation.raw_evidence.locator
                    if observation
                    else event.provenance.source_url,
                    "account_id": subject.canonical_account_id,
                    "program_name": event.program.mention,
                    "program_id": event.program.canonical_program_id,
                    "facility_id": event.canonical_facility_id,
                    "evidence_state": event.provenance.evidence_state,
                    "resolution_state": event.resolution_state,
                    "data_mode": event.provenance.data_mode,
                    "observed_at": event.event_date or event.provenance.observed_at,
                    "relevance_explanation": business.why_it_may_matter
                    if business
                    else "Account-specific analysis is incomplete; the source is retained without a commercial recommendation.",
                    "business_briefing": jsonable_encoder(business)
                    if business
                    else None,
                    "evidence_ids": tuple(item.evidence_id for item in event.evidence),
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
