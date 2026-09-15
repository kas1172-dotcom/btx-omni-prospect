"""Explicit live collection orchestration. Disabled mode performs no network I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

from btx_omni.core.config import Settings
from btx_omni.monitor.candidates import (
    organization_candidate_for,
    program_candidate_for,
)
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.clustering import cluster_event, cluster_key, observation_changed
from btx_omni.monitor.contracts import (
    CollectionCursor,
    CollectionRun,
    EventCluster,
    IntelligenceEvent,
    RejectedObservation,
    SourceHealth,
    SourceObservation,
    SourceOperationalStatus,
)
from btx_omni.monitor.documents import (
    enrich_feed_documents,
    retain_document_after_failed_refresh,
)
from btx_omni.monitor.entity_candidates import EntityCandidateResolver
from btx_omni.monitor.funnel import collection_funnel
from btx_omni.monitor.health import SOURCE_HEALTH_WARNING
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import EventType, SourceHealthState
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.sources import REGISTRY, LiveSourceAdapter
from btx_omni.monitor.targeting import WatchTarget
from btx_omni.monitor.usaspending import normalize_usaspending_observation
from btx_omni.providers.research.deadline import (
    PublicReadDeadlineExceeded as CollectionDeadlineExceeded,
)
from btx_omni.providers.research.deadline import bounded_public_read


def current_event_contexts(monitor):
    """Read one immutable canonical snapshot; never cache a worker's public writes."""
    if getattr(monitor, "repository", None):
        return monitor.repository.event_contexts()
    observations = {
        item.raw_evidence.id: item
        for item in getattr(monitor, "observations", {}).values()
    }
    return tuple(
        (
            event,
            next(
                (
                    observations[item.evidence_id]
                    for item in event.evidence
                    if item.evidence_id in observations
                ),
                None,
            ),
        )
        for event in tuple(monitor.events.values())
    )


def current_source_observations(monitor):
    """Canonical current observations for existing source-specific projections."""
    if not getattr(monitor, "repository", None):
        return tuple(monitor.observations.values())
    return tuple(
        {
            observation.id: observation
            for _event, observation in current_event_contexts(monitor)
            if observation is not None
        }.values()
    )


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
    source_versions: dict[tuple[str, str], SourceObservation] = field(
        default_factory=dict
    )
    repository: MonitorRepository | None = None
    watch_profiles: tuple[AccountWatchProfile, ...] = ()
    catalog: MonitorCatalog = field(default_factory=MonitorCatalog)
    watch_targets: dict[str, tuple[WatchTarget, ...]] = field(default_factory=dict)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    entity_candidate_resolver: EntityCandidateResolver | None = None

    @staticmethod
    def _collect_with_deadline(
        adapter: LiveSourceAdapter,
        *,
        run_id: str,
        settings: Settings,
        limit: int,
        collected_at: datetime,
        deadline_monotonic: float | None,
    ) -> list[SourceObservation]:
        """Execute only the adapter call within the worker's bounded budget.

        A signal interrupts supported Unix main-thread calls.  Other hosts use
        a daemon thread solely for the adapter call; state is never shared with
        that thread, so a late result cannot mutate Monitor state.
        """

        def invoke() -> list[SourceObservation]:
            observations = adapter.collect(
                run_id=run_id,
                settings=settings,
                limit=limit,
                collected_at=collected_at,
            )
            if any(
                kind in adapter.definition.content_structure for kind in ("RSS", "FEED")
            ):
                observations = enrich_feed_documents(
                    observations,
                    fetch=adapter.get,
                    cap=settings.monitor_document_fetch_cap,
                )
            return observations

        return bounded_public_read(invoke, deadline_monotonic)

    def collect(
        self,
        source_id: str,
        limit: int = 10,
        *,
        deadline_monotonic: float | None = None,
    ) -> CollectionRun:
        if self.settings.monitor_mode.lower() != "live":
            raise RuntimeError(
                "MONITOR_MODE is disabled; live collection was not attempted"
            )
        adapter = self.registry[source_id]
        started, started_monotonic, run_id = self.clock(), monotonic(), str(uuid4())
        previous_health = self.health.get(source_id)
        if previous_health is None and self.repository:
            durable_health = next(
                (
                    item
                    for item in self.repository.snapshot()["health"]
                    if item["source_id"] == source_id
                ),
                None,
            )
            previous_success = (
                durable_health.get("last_success_at") if durable_health else None
            )
        else:
            previous_success = (
                previous_health.last_success_at if previous_health else None
            )
        try:
            observations = self._collect_with_deadline(
                adapter,
                run_id=run_id,
                settings=self.settings,
                limit=limit,
                collected_at=started,
                deadline_monotonic=deadline_monotonic,
            )
            retained_observations = []
            for observation in observations:
                key = (
                    observation.source_identity.source_system,
                    observation.source_identity.source_record_id,
                )
                previous = self.source_versions.get(key)
                previous_payload = (
                    previous.structured_payload
                    if previous
                    else (
                        self.repository.source_observation_payload(*key)
                        if self.repository
                        else None
                    )
                )
                retained_observations.append(
                    retain_document_after_failed_refresh(observation, previous_payload)
                )
            observations = retained_observations
            created = changed = new = rejected_count = 0
            persisted_events: list[IntelligenceEvent] = []
            organization_candidates = []
            program_candidates = []
            for observation in observations:
                if source_id == "usaspending":
                    usa_decision = normalize_usaspending_observation(
                        observation,
                        profiles=self.watch_profiles,
                        catalog=self.catalog,
                        now=started,
                    )
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
                if self.entity_candidate_resolver:
                    candidate = replace(
                        candidate,
                        event=self.entity_candidate_resolver.apply(
                            candidate.event, observation
                        ),
                    )
                self.observations[observation.id] = observation
                self.events[candidate.event.id] = candidate.event
                persisted_events.append(candidate.event)
                organization_candidate = None
                if self.repository:
                    organization_candidate = organization_candidate_for(
                        candidate.event, observation
                    )
                    if organization_candidate:
                        organization_candidate = organization_candidate_for(
                            candidate.event,
                            observation,
                            existing=self.repository.organization_candidate(
                                organization_candidate.identity_key
                            ),
                        )
                        organization_candidates.append(organization_candidate)
                    program_candidate = program_candidate_for(
                        candidate.event,
                        observation,
                        organization_candidate=organization_candidate,
                    )
                    if program_candidate:
                        program_candidate = program_candidate_for(
                            candidate.event,
                            observation,
                            organization_candidate=organization_candidate,
                            existing=self.repository.program_candidate(
                                program_candidate.identity_key
                            ),
                        )
                        program_candidates.append(program_candidate)
                version_key = (
                    observation.source_identity.source_system,
                    observation.source_identity.source_record_id,
                )
                previous = self.source_versions.get(version_key)
                # Source adapters construct a fresh observation on every run.
                # Preserve governed first-seen history when the same canonical
                # source record reappears; this is consumed by procurement
                # period comparisons and is not inferred from source text.
                if previous is not None:
                    observation = replace(
                        observation,
                        source_version=replace(
                            observation.source_version,
                            first_seen_at=previous.source_version.first_seen_at,
                            last_seen_at=observation.observed_at,
                            changed_at=(
                                observation.observed_at
                                if observation_changed(previous, observation)
                                else previous.source_version.changed_at
                            ),
                        ),
                    )
                persisted_hash = (
                    self.repository.source_content_hash(*version_key)
                    if previous is None and self.repository
                    else None
                )
                changed += int(
                    observation_changed(previous, observation)
                    or (
                        persisted_hash is not None
                        and persisted_hash != observation.source_version.content_hash
                    )
                )
                new += int(previous is None and persisted_hash is None)
                self.source_versions[version_key] = observation
                cluster_id = cluster_key(candidate.event)
                existing_cluster = self.clusters.get(cluster_id) or (
                    self.repository.cluster(cluster_id) if self.repository else None
                )
                decision = cluster_event(candidate.event, observation, existing_cluster)
                self.clusters[cluster_id] = decision.cluster
                created += int(decision.created)
            completed = self.clock()
            cursor = CollectionCursor(
                source_id, token=completed.isoformat(), page=1, updated_at=completed
            )
            warning_reader = getattr(adapter, "collection_warnings", None)
            warnings = tuple(warning_reader()) if callable(warning_reader) else ()
            run = CollectionRun(
                run_id,
                source_id,
                started,
                completed,
                cursor,
                records_seen=len(observations),
                records_new=new,
                records_changed=changed,
                records_rejected=rejected_count,
                events_created=created,
                events_matched=len(observations) - created,
                failures=warnings,
                latency_ms=round((monotonic() - started_monotonic) * 1000),
            )
            self.health[source_id] = SourceHealth(
                source_id,
                SourceHealthState.PARTIAL if warnings else SourceHealthState.HEALTHY,
                started,
                run.completed_at,
                SOURCE_HEALTH_WARNING if warnings else None,
                "; ".join(warnings) if warnings else None,
            )
        except PermissionError as exc:
            detail = self._safe_failure(exc)
            run = CollectionRun(
                run_id,
                source_id,
                started,
                self.clock(),
                None,
                failures=(detail,),
                latency_ms=round((monotonic() - started_monotonic) * 1000),
            )
            self.health[source_id] = SourceHealth(
                source_id,
                SourceHealthState.WARNING,
                started,
                previous_success,
                SOURCE_HEALTH_WARNING,
                detail,
            )
        except Exception as exc:  # noqa: BLE001 - adapter boundary records all source failures as health
            detail = self._safe_failure(exc)
            run = CollectionRun(
                run_id,
                source_id,
                started,
                self.clock(),
                None,
                failures=(detail,),
                latency_ms=round((monotonic() - started_monotonic) * 1000),
            )
            self.health[source_id] = SourceHealth(
                source_id,
                SourceHealthState.FAILED,
                started,
                previous_success,
                SOURCE_HEALTH_WARNING,
                detail,
            )
        run = replace(
            run,
            funnel=collection_funnel(
                observations if "observations" in locals() else (),
                persisted_events if "persisted_events" in locals() else (),
                complete=not run.failures,
                failures=run.failures,
            ),
        )
        self.runs.append(run)
        if self.repository:
            self.repository.persist_snapshot(
                run=run,
                health=self.health[source_id],
                observations=tuple(observations) if "observations" in locals() else (),
                events=tuple(persisted_events)
                if "persisted_events" in locals()
                else (),
                clusters=tuple(self.clusters.values()),
                rejected=tuple(self.rejected),
                organization_candidates=tuple(organization_candidates)
                if "organization_candidates" in locals()
                else (),
                program_candidates=tuple(program_candidates)
                if "program_candidates" in locals()
                else (),
            )
        return run

    def collect_all(
        self, *, source_ids: tuple[str, ...] | None = None, limit: int = 10
    ) -> tuple[CollectionRun, ...]:
        """Run every requested registered provider through the sole collection path.

        A future scheduler need only invoke this method (or the protected API
        endpoint that delegates to it); no second ingestion workflow exists.
        """
        identifiers = source_ids or tuple(self.registry)
        unknown = set(identifiers) - set(self.registry)
        if unknown:
            raise KeyError(f"unknown Monitor sources: {sorted(unknown)}")
        return tuple(self.collect(source_id, limit=limit) for source_id in identifiers)

    @staticmethod
    def _safe_failure(error: Exception) -> str:
        if isinstance(error, PermissionError):
            return str(error)[:240]
        message = str(error)
        if message in {
            "RATE_LIMITED",
            "MALFORMED_SOURCE_RESPONSE",
        } or message.startswith("HTTP_"):
            return message
        if isinstance(error, CollectionDeadlineExceeded):
            return "DEADLINE_EXCEEDED"
        return f"{type(error).__name__}: collection failed"

    def durable_snapshot(self) -> dict[str, tuple[dict, ...]] | None:
        if not self.repository:
            return None
        return self.repository.snapshot()

    def hydrate_events(self) -> None:
        """Replace transient event state with the durable canonical snapshot."""
        if self.repository:
            self.events = {event.id: event for event in self.repository.events()}

    def source_state(
        self, *, source_id: str, last_success_at: datetime | None, now: datetime
    ) -> str:
        if last_success_at is None:
            return "UNAVAILABLE"
        # SQLite drops timezone information while PostgreSQL preserves it. Treat
        # persisted Monitor timestamps as UTC at this boundary so readiness and
        # freshness semantics are identical in local tests and production.
        if last_success_at.tzinfo is None:
            last_success_at = last_success_at.replace(tzinfo=UTC)
        if now - last_success_at > timedelta(
            hours=self.freshness_threshold_hours(source_id)
        ):
            return "STALE"
        return "HEALTHY"

    def freshness_threshold_hours(self, source_id: str) -> int:
        cadence = (
            self.registry.get(source_id).definition.cadence.casefold()
            if source_id in self.registry
            else ""
        )
        expected_hours = (
            2
            if "hour" in cadence
            else 26
            if "daily" in cadence
            else 192
            if "week" in cadence
            else self.settings.monitor_stale_after_hours
        )
        configured = (
            self.registry[source_id].definition.freshness_threshold_hours
            if source_id in self.registry
            else expected_hours
        )
        return min(expected_hours, configured, self.settings.monitor_stale_after_hours)

    def operational_status(
        self,
        source_id: str,
        *,
        now: datetime | None = None,
        durable_health: dict | None = None,
        last_run: dict | None = None,
    ) -> SourceOperationalStatus:
        clock = now or datetime.now(UTC)
        adapter = self.registry[source_id]
        available, unavailable_reason = adapter.available(self.settings)
        health = durable_health or self.health.get(source_id)
        last_attempt = (
            health.get("last_attempt_at")
            if isinstance(health, dict)
            else getattr(health, "last_attempt_at", None)
        )
        last_success = (
            health.get("last_success_at")
            if isinstance(health, dict)
            else getattr(health, "last_success_at", None)
        )
        detail = (
            health.get("detail")
            if isinstance(health, dict)
            else getattr(health, "detail", None)
        )
        persisted = (
            health.get("state")
            if isinstance(health, dict)
            else getattr(health, "state", None)
        )
        persisted_value = str(getattr(persisted, "value", persisted))
        if self.settings.monitor_mode.lower() != "live":
            state = SourceHealthState.DISABLED
        elif not available:
            state, detail = SourceHealthState.NOT_CONFIGURED, unavailable_reason
        elif last_attempt is None:
            state = SourceHealthState.NEVER_ATTEMPTED
        elif not last_success or persisted_value == "FAILED":
            state = SourceHealthState.FAILED
        elif persisted_value in {"WARNING", "PARTIAL"}:
            state = SourceHealthState.PARTIAL
        elif (
            self.source_state(
                source_id=source_id, last_success_at=last_success, now=clock
            )
            == "STALE"
        ):
            state = SourceHealthState.STALE
        else:
            state = SourceHealthState.HEALTHY
        run = last_run or {}
        return SourceOperationalStatus(
            source_id,
            adapter.definition.source_name,
            state,
            available
            and self.settings.monitor_mode.lower() == "live"
            and bool(self.repository),
            adapter.definition.content_structure,
            adapter.definition.authentication_requirement,
            tuple(
                reason.code
                for target in self.watch_targets.get(source_id, ())
                for reason in target.reasons
            ),
            self.freshness_threshold_hours(source_id),
            last_attempt,
            last_success,
            detail,
            bool(self.repository),
            int(run.get("records_seen", 0)),
            int(run.get("events_created", 0)),
            adapter.definition.seller_promotion_permitted,
        )
