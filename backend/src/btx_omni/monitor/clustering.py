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
    # Same company/type/date is not the same event. In particular, unresolved
    # feed items must never corroborate each other through a generic publisher.
    # Cross-source equivalence requires a separately verified event identifier;
    # this conservative version only groups versions of one publisher record.
    source = event.provenance
    identity = ("BTX_SOURCE_RECORD_CLUSTER_2", source.source_system, source.source_record_id)
    return sha256(repr(identity).encode()).hexdigest()[:24]


def cluster_event(event: IntelligenceEvent, observation: SourceObservation, existing: EventCluster | None = None) -> ClusterDecision:
    if existing is None:
        cluster = EventCluster(cluster_key(event), event.id, (observation.id,), (observation.raw_evidence.id,))
        return ClusterDecision(cluster, True, False)
    if existing.id != cluster_key(event):
        raise ValueError("Cannot merge a different source record into this cluster")
    observations = tuple(dict.fromkeys((*existing.observation_ids, observation.id)))
    evidence = tuple(dict.fromkeys((*existing.evidence_ids, observation.raw_evidence.id)))
    prior_versions = tuple(dict.fromkeys((*existing.related_event_ids, *([existing.event_id] if existing.event_id != event.id else []))))
    return ClusterDecision(EventCluster(existing.id, event.id, observations, evidence, prior_versions, existing.ambiguity_reason), False, existing.event_id != event.id)
