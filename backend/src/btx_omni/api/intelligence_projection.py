"""Projects canonical stored and live Monitor intelligence through one API contract."""
from __future__ import annotations

from fastapi.encoders import jsonable_encoder

from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.intelligence.signals import normalize_signal


def intelligence_signals(runtime: PocRuntime) -> list[dict]:
    sample = runtime.environment()
    names = {item.legal_name: item.id for item in sample.accounts}
    accounts = {item.id: item for item in sample.accounts}
    stored = [
        normalize_signal(item, account_name_to_id=names, provenance=accounts[names[item.account_name]].provenance)
        for item in sample.intelligence_events
        if item.account_name in names and names[item.account_name] in sample.rich_scenarios
    ]
    live: list[dict] = []
    for event in runtime.monitor.events.values():
        subject = event.subject_entities[0] if event.subject_entities else None
        if event.seller_relevance_state.value != "RESOLVED_ELIGIBLE" or event.resolution_state.value != "RESOLVED" or not subject or not subject.canonical_account_id:
            continue
        evidence_ids = {evidence.evidence_id for evidence in event.evidence}
        observation = next((item for item in runtime.monitor.observations.values() if item.raw_evidence.id in evidence_ids), None)
        live.append({
            "id": event.id,
            "kind": event.event_type.value,
            "title": next((claim.value for claim in event.claims if claim.predicate == "source_title"), event.event_type.value),
            "source_url": observation.raw_evidence.locator if observation else event.provenance.source_url,
            "account_id": subject.canonical_account_id if subject else None,
            "program_name": event.program.mention,
            "program_id": event.program.canonical_program_id,
            "facility_id": event.canonical_facility_id,
            "evidence_state": event.provenance.evidence_state,
            "resolution_state": event.resolution_state,
            "data_mode": event.provenance.data_mode,
            "observed_at": event.event_date or event.provenance.observed_at,
            "relevance_explanation": (f"Live public {event.event_type.value}; " + ("linked to a canonical account." if subject and subject.canonical_account_id else "entity remains unresolved; no account relationship is implied.")),
            "evidence_ids": tuple(item.evidence_id for item in event.evidence),
            "source_tier": event.source_confidence_basis,
            "provenance": event.provenance,
        })
    return [*({**jsonable_encoder(item), "observed_at": item.occurred_at, "data_mode": "CURATED_PUBLIC", "source_tier": "CURATED_POC_PUBLIC"} for item in stored), *live]
