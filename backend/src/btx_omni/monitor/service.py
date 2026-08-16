"""Explicit live collection orchestration. Disabled mode performs no network I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from btx_omni.core.config import Settings
from btx_omni.monitor.clustering import cluster_event, cluster_key, observation_changed
from btx_omni.monitor.contracts import (
    CollectionRun,
    EventCluster,
    IntelligenceEvent,
    RejectedObservation,
    SourceHealth,
    SourceObservation,
)
from btx_omni.monitor.health import SOURCE_HEALTH_WARNING
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import SourceHealthState
from btx_omni.monitor.sources import REGISTRY, LiveSourceAdapter


@dataclass
class MonitorService:
    settings: Settings
    registry: dict[str, LiveSourceAdapter] = field(default_factory=lambda: REGISTRY)
    health: dict[str, SourceHealth] = field(default_factory=dict)
    runs: list[CollectionRun] = field(default_factory=list)
    clusters: dict[str, EventCluster] = field(default_factory=dict)
    events: dict[str, IntelligenceEvent] = field(default_factory=dict)
    observations: dict[str, SourceObservation] = field(default_factory=dict)
    rejected: list[RejectedObservation] = field(default_factory=list)
    source_versions: dict[tuple[str, str], SourceObservation] = field(default_factory=dict)

    def collect(self, source_id: str, limit: int = 10) -> CollectionRun:
        if self.settings.monitor_mode.lower() != "live":
            raise RuntimeError("MONITOR_MODE is disabled; live collection was not attempted")
        adapter = self.registry[source_id]
        started, clock, run_id = datetime.now(UTC), perf_counter(), str(uuid4())
        try:
            observations = adapter.collect(run_id=run_id, settings=self.settings, limit=limit)
            created = changed = new = 0
            for observation in observations:
                candidate = normalize_structured_observation(observation)
                self.observations[observation.id] = observation
                self.events[candidate.event.id] = candidate.event
                version_key = (observation.source_identity.source_system, observation.source_identity.source_record_id)
                previous = self.source_versions.get(version_key)
                changed += int(observation_changed(previous, observation))
                new += int(previous is None)
                self.source_versions[version_key] = observation
                cluster_id = cluster_key(candidate.event)
                decision = cluster_event(candidate.event, observation, self.clusters.get(cluster_id))
                self.clusters[cluster_id] = decision.cluster
                created += int(decision.created)
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, records_seen=len(observations), records_new=new, records_changed=changed, events_created=created, events_matched=len(observations) - created, latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.HEALTHY, started, run.completed_at)
        except PermissionError as exc:
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, failures=(str(exc),), latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.WARNING, started, None, SOURCE_HEALTH_WARNING, str(exc))
        except Exception as exc:  # noqa: BLE001 - adapter boundary records all source failures as health
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, failures=(str(exc),), latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.FAILED, started, None, SOURCE_HEALTH_WARNING, str(exc))
        self.runs.append(run)
        return run
