"""Deterministic clustering; persistence may replace these in-memory decisions later."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from btx_omni.monitor.contracts import (
    EventCluster,
    IntelligenceEvent,
    SourceObservation,
)


@dataclass(frozen=True)
class ClusterDecision:
    cluster: EventCluster
    created: bool
    source_record_changed: bool


def observation_changed(previous: SourceObservation | None, current: SourceObservation) -> bool:
    return previous is not None and previous.source_version.content_hash != current.source_version.content_hash


def cluster_key(event: IntelligenceEvent) -> str:
    subjects = sorted(item.canonical_account_id or item.mention.casefold() for item in event.subject_entities)
    date = event.event_date.date().isoformat() if event.event_date else "unknown-date"
    program = event.program.canonical_program_id or (event.program.mention or "").casefold()
    return sha256("|".join((event.event_type.value, ",".join(subjects), program, date)).encode()).hexdigest()[:24]


def cluster_event(event: IntelligenceEvent, observation: SourceObservation, existing: EventCluster | None = None) -> ClusterDecision:
    if existing is None:
        cluster = EventCluster(cluster_key(event), event.id, (observation.id,), (observation.raw_evidence.id,))
        return ClusterDecision(cluster, True, False)
    observations = tuple(dict.fromkeys((*existing.observation_ids, observation.id)))
    evidence = tuple(dict.fromkeys((*existing.evidence_ids, observation.raw_evidence.id)))
    return ClusterDecision(EventCluster(existing.id, existing.event_id, observations, evidence, existing.related_event_ids, existing.ambiguity_reason), False, False)
