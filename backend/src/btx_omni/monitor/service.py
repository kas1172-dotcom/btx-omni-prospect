"""Explicit live collection orchestration. Disabled mode performs no network I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

from btx_omni.core.config import Settings
from btx_omni.monitor.catalog import MonitorCatalog
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
from btx_omni.monitor.ontology import EventType, SourceHealthState
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.sources import REGISTRY, LiveSourceAdapter
from btx_omni.monitor.usaspending import normalize_usaspending_observation


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
    repository: MonitorRepository | None = None
    watch_profiles: tuple[AccountWatchProfile, ...] = ()
    catalog: MonitorCatalog = field(default_factory=MonitorCatalog)

    def collect(self, source_id: str, limit: int = 10) -> CollectionRun:
        if self.settings.monitor_mode.lower() != "live":
            raise RuntimeError("MONITOR_MODE is disabled; live collection was not attempted")
        adapter = self.registry[source_id]
        started, clock, run_id = datetime.now(UTC), perf_counter(), str(uuid4())
        try:
            observations = adapter.collect(run_id=run_id, settings=self.settings, limit=limit)
            created = changed = new = rejected_count = 0
            persisted_events: list[IntelligenceEvent] = []
            for observation in observations:
                if source_id == "usaspending":
                    usa_decision = normalize_usaspending_observation(observation, profiles=self.watch_profiles, catalog=self.catalog, now=started)
                    candidate = usa_decision
                    if usa_decision.rejected:
                        self.rejected.append(usa_decision.rejected)
                        rejected_count += 1
                else:
                    source_event_type = {
                        "fda_openfda": EventType.REGULATORY_APPROVAL,
                        "federal_register": EventType.REGULATORY_CHANGE,
                    }.get(source_id)
                    candidate = normalize_structured_observation(
                        observation,
                        event_type=source_event_type,
                        catalog=self.catalog,
                        source_markets=adapter.definition.industries_supported,
                        now=started,
                    )
                self.observations[observation.id] = observation
                self.events[candidate.event.id] = candidate.event
                persisted_events.append(candidate.event)
                version_key = (observation.source_identity.source_system, observation.source_identity.source_record_id)
                previous = self.source_versions.get(version_key)
                persisted_hash = self.repository.source_content_hash(*version_key) if previous is None and self.repository else None
                changed += int(observation_changed(previous, observation) or (persisted_hash is not None and persisted_hash != observation.source_version.content_hash))
                new += int(previous is None and persisted_hash is None)
                self.source_versions[version_key] = observation
                cluster_id = cluster_key(candidate.event)
                existing_cluster = self.clusters.get(cluster_id) or (self.repository.cluster(cluster_id) if self.repository else None)
                decision = cluster_event(candidate.event, observation, existing_cluster)
                self.clusters[cluster_id] = decision.cluster
                created += int(decision.created)
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, records_seen=len(observations), records_new=new, records_changed=changed, records_rejected=rejected_count, events_created=created, events_matched=len(observations) - created, latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.HEALTHY, started, run.completed_at)
        except PermissionError as exc:
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, failures=(str(exc),), latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.WARNING, started, None, SOURCE_HEALTH_WARNING, str(exc))
        except Exception as exc:  # noqa: BLE001 - adapter boundary records all source failures as health
            run = CollectionRun(run_id, source_id, started, datetime.now(UTC), None, failures=(str(exc),), latency_ms=round((perf_counter() - clock) * 1000))
            self.health[source_id] = SourceHealth(source_id, SourceHealthState.FAILED, started, None, SOURCE_HEALTH_WARNING, str(exc))
        self.runs.append(run)
        if self.repository:
            self.repository.persist_snapshot(run=run, health=self.health[source_id], observations=tuple(observations) if 'observations' in locals() else (), events=tuple(persisted_events) if 'persisted_events' in locals() else (), clusters=tuple(self.clusters.values()), rejected=tuple(self.rejected))
        return run

    def collect_all(self, *, source_ids: tuple[str, ...] | None = None, limit: int = 10) -> tuple[CollectionRun, ...]:
        """Run every requested registered provider through the sole collection path.

        A future scheduler need only invoke this method (or the protected API
        endpoint that delegates to it); no second ingestion workflow exists.
        """
        identifiers = source_ids or tuple(self.registry)
        unknown = set(identifiers) - set(self.registry)
        if unknown:
            raise KeyError(f"unknown Monitor sources: {sorted(unknown)}")
        return tuple(self.collect(source_id, limit=limit) for source_id in identifiers)

    def durable_snapshot(self) -> dict[str, tuple[dict, ...]] | None:
        if not self.repository:
            return None
        return self.repository.snapshot()

    def source_state(self, *, source_id: str, last_success_at: datetime | None, now: datetime) -> str:
        if last_success_at is None:
            return "UNAVAILABLE"
        cadence = self.registry.get(source_id).definition.cadence.casefold() if source_id in self.registry else ""
        expected_hours = 2 if "hour" in cadence else 26 if "daily" in cadence else 192 if "week" in cadence else self.settings.monitor_stale_after_hours
        if now - last_success_at > timedelta(hours=min(expected_hours, self.settings.monitor_stale_after_hours)):
            return "STALE"
        return "HEALTHY"
