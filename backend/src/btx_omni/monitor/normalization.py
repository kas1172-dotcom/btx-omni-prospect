"""Deterministic source-to-event candidate normalization; AI is not used for JSON reformatting."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.candidates import explicit_program_mention
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.contracts import (
    EventEvidence,
    IntelligenceEvent,
    NormalizedClaim,
    ProgramResolution,
    SourceObservation,
)
from btx_omni.monitor.ontology import EventType, ResolutionState
from btx_omni.monitor.policy import classify_markets, recency_state, seller_relevance
from btx_omni.monitor.resolution import resolve_entity


def classify_title(title: str) -> EventType:
    value = title.casefold()
    rules = (("modification", EventType.CONTRACT_MODIFICATION), ("solicitation", EventType.SOLICITATION), ("award", EventType.CONTRACT_AWARD), ("grant", EventType.GRANT_AWARD), ("funding", EventType.GOVERNMENT_FUNDING), ("approval", EventType.REGULATORY_APPROVAL), ("facility", EventType.NEW_FACILITY), ("capacity", EventType.CAPACITY_EXPANSION), ("partnership", EventType.PARTNERSHIP), ("acquisition", EventType.M_AND_A), ("earnings", EventType.EARNINGS_SIGNAL), ("backlog", EventType.BACKLOG_CHANGE), ("launch", EventType.PRODUCT_LAUNCH))
    return next((event_type for needle, event_type in rules if needle in value), EventType.SUPPLY_CHAIN_CHANGE)


@dataclass(frozen=True)
class EventCandidate:
    event: IntelligenceEvent
    extraction_method: str


def normalize_structured_observation(
    observation: SourceObservation,
    *,
    subject_mention: str | None = None,
    event_type: EventType | None = None,
    catalog: MonitorCatalog | None = None,
    source_markets: tuple[str, ...] = (),
    now: datetime | None = None,
) -> EventCandidate:
    kind = event_type or classify_title(observation.title)
    catalog = catalog or MonitorCatalog()
    source_text = "\n".join(part for part in (observation.title, observation.structured_payload or "") if part)
    subjects = (
        (resolve_entity(subject_mention, catalog.profiles, source_identifiers=observation.source_identity.source_native_ids, source_url=observation.raw_payload_locator),)
        if subject_mention
        else catalog.resolve_subjects(source_text)
    )
    resolution = subjects[0].state if len(subjects) == 1 else ResolutionState.AMBIGUOUS
    program = catalog.resolve_program(source_text)
    source_program = explicit_program_mention(observation)
    if source_program and program.canonical_program_id is None:
        program = ProgramResolution(
            source_program,
            None,
            program.state,
            "source_structured_program_name",
            "source record explicitly supplies this program name; no canonical Program was resolved",
        )
    markets = classify_markets(source_text, source_markets=source_markets)
    freshness = recency_state(observation.source_published_at, now=now)
    claim = NormalizedClaim("source_title", observation.title, (observation.raw_evidence.id,), "deterministic_structured_mapping", "preserved source field")
    provenance = Provenance(observation.source_identity.source_system, observation.source_identity.source_record_id, observation.raw_evidence.locator, observation.observed_at, datetime.now(UTC), Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
    event = IntelligenceEvent(
        f"event-{observation.id.removeprefix('observation-')}",
        kind,
        subjects,
        (),
        program,
        None,
        observation.source_published_at,
        None,
        None,
        (claim,),
        (EventEvidence(observation.raw_evidence.id, ("source_title",), "PRIMARY"),),
        provenance,
        observation.source_tier,
        "deterministic structured mapping",
        subjects[0].confidence_basis,
        "one source",
        resolution,
        seller_relevance_state=seller_relevance(markets=markets, event_type=kind, event_date=observation.source_published_at, resolution_state=resolution, source_text=source_text, now=now),
        markets=markets,
        recency_state=freshness,
        canonical_facility_id=catalog.resolve_facility_id(source_text),
    )
    return EventCandidate(event, "deterministic_structured_mapping")
