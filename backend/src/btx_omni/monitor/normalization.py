"""Deterministic source-to-event candidate normalization; AI is not used for JSON reformatting."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.contracts import (
    EntityResolution,
    EventEvidence,
    IntelligenceEvent,
    NormalizedClaim,
    ProgramResolution,
    SourceObservation,
)
from btx_omni.monitor.ontology import EventType, ResolutionState


def classify_title(title: str) -> EventType:
    value = title.casefold()
    rules = (("modification", EventType.CONTRACT_MODIFICATION), ("solicitation", EventType.SOLICITATION), ("award", EventType.CONTRACT_AWARD), ("grant", EventType.GRANT_AWARD), ("funding", EventType.GOVERNMENT_FUNDING), ("approval", EventType.REGULATORY_APPROVAL), ("facility", EventType.NEW_FACILITY), ("capacity", EventType.CAPACITY_EXPANSION), ("partnership", EventType.PARTNERSHIP), ("acquisition", EventType.M_AND_A), ("earnings", EventType.EARNINGS_SIGNAL), ("backlog", EventType.BACKLOG_CHANGE), ("launch", EventType.PRODUCT_LAUNCH))
    return next((event_type for needle, event_type in rules if needle in value), EventType.SUPPLY_CHAIN_CHANGE)


@dataclass(frozen=True)
class EventCandidate:
    event: IntelligenceEvent
    extraction_method: str


def normalize_structured_observation(observation: SourceObservation, *, subject_mention: str | None = None, event_type: EventType | None = None) -> EventCandidate:
    kind = event_type or classify_title(observation.title)
    subject = EntityResolution(subject_mention or "unresolved source subject", None, ResolutionState.UNRESOLVED, "structured_source", "source record has no matched canonical identifier")
    claim = NormalizedClaim("source_title", observation.title, (observation.raw_evidence.id,), "deterministic_structured_mapping", "preserved source field")
    provenance = Provenance(observation.source_identity.source_system, observation.source_identity.source_record_id, observation.raw_evidence.locator, observation.observed_at, datetime.now(UTC), Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False)
    event = IntelligenceEvent(f"event-{observation.id.removeprefix('observation-')}", kind, (subject,), (), ProgramResolution(None, None, ResolutionState.UNRESOLVED, "not_present", "no source program field"), None, observation.source_published_at, None, None, (claim,), (EventEvidence(observation.raw_evidence.id, ("source_title",), "PRIMARY"),), provenance, observation.source_tier, "deterministic structured mapping", "unresolved pending account watch matching", "one source", ResolutionState.UNRESOLVED)
    return EventCandidate(event, "deterministic_structured_mapping")
