"""Durable Monitor state boundary; API routes never issue database queries directly."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Engine, case, delete, insert, or_, select, text, true, update

from btx_omni.core.classification import Classification, SensitivityTag
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.contracts import (
    CollectionRun,
    EntityResolution,
    EventCluster,
    EventEvidence,
    IntelligenceEvent,
    NormalizedClaim,
    OrganizationCandidate,
    ProgramCandidate,
    ProgramResolution,
    RawEvidenceReference,
    RejectedObservation,
    SourceHealth,
    SourceIdentity,
    SourceObservation,
    SourceVersion,
)
from btx_omni.monitor.ontology import (
    CandidateReviewState,
    EventType,
    ResolutionState,
    SellerRelevanceState,
)
from btx_omni.monitor.research_state import MonitorResearchJournal
from btx_omni.persistence.models import (
    governed_explanations,
    monitor_brief_syntheses,
    monitor_candidate_promotion_audits,
    monitor_collection_runs,
    monitor_entity_candidate_resolutions,
    monitor_event_clusters,
    monitor_events,
    monitor_intelligence_assessments,
    monitor_observations,
    monitor_organization_candidates,
    monitor_program_candidate_promotion_audits,
    monitor_program_candidates,
    monitor_rejected_observations,
    monitor_source_health,
    monitor_source_versions,
    monitor_technical_decompositions,
)


def _json(value: object) -> str:
    def encode(item: object) -> object:
        if hasattr(item, "value"):
            return item.value  # type: ignore[no-any-return]
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, Decimal):
            return str(item)
        if isinstance(item, frozenset):
            return sorted(item)
        raise TypeError(f"unsupported Monitor persistence value: {type(item).__name__}")

    return json.dumps(
        asdict(value) if hasattr(value, "__dataclass_fields__") else value,
        default=encode,
        sort_keys=True,
    )


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _database_timestamp(value: datetime) -> datetime:
    """Restore SQLite's timezone-less DATETIME values as their persisted UTC instants."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _event_from_payload(payload: str) -> IntelligenceEvent:
    """Restore the canonical event exactly as it was persisted.

    Hydration deliberately deserializes the stored canonical payload; it does
    not repeat entity, program, or relevance resolution at runtime startup.
    """
    value = json.loads(payload)
    provenance = value["provenance"]
    return IntelligenceEvent(
        id=value["id"],
        event_type=EventType(value["event_type"]),
        subject_entities=tuple(
            EntityResolution(
                item["mention"],
                item.get("canonical_account_id"),
                ResolutionState(item["state"]),
                item["method"],
                item["confidence_basis"],
                tuple(item.get("candidate_account_ids", ())),
            )
            for item in value["subject_entities"]
        ),
        related_entities=tuple(
            EntityResolution(
                item["mention"],
                item.get("canonical_account_id"),
                ResolutionState(item["state"]),
                item["method"],
                item["confidence_basis"],
                tuple(item.get("candidate_account_ids", ())),
            )
            for item in value["related_entities"]
        ),
        program=ProgramResolution(
            value["program"].get("mention"),
            value["program"].get("canonical_program_id"),
            ResolutionState(value["program"]["state"]),
            value["program"]["method"],
            value["program"]["confidence_basis"],
        ),
        geography=value.get("geography"),
        event_date=_timestamp(value.get("event_date")),
        source_published_at=_timestamp(value.get("source_published_at")),
        amount=Decimal(value["amount"]) if value.get("amount") is not None else None,
        currency=value.get("currency"),
        claims=tuple(
            NormalizedClaim(
                item["predicate"],
                item["value"],
                tuple(item["evidence_ids"]),
                item["extraction_method"],
                item["extraction_confidence"],
            )
            for item in value["claims"]
        ),
        evidence=tuple(
            EventEvidence(
                item["evidence_id"], tuple(item["claim_predicates"]), item["role"]
            )
            for item in value["evidence"]
        ),
        provenance=Provenance(
            provenance["source_system"],
            provenance["source_record_id"],
            provenance.get("source_url"),
            _timestamp(provenance["observed_at"]),  # type: ignore[arg-type]
            _timestamp(provenance["recorded_at"]),  # type: ignore[arg-type]
            Classification(provenance["classification"]),
            EvidenceState(provenance["evidence_state"]),
            DataMode(provenance["data_mode"]),
            provenance["synthetic"],
            frozenset(
                SensitivityTag(item) for item in provenance.get("sensitivity_tags", ())
            ),
            tuple(provenance.get("missing_fields", ())),
        ),
        source_confidence_basis=value["source_confidence_basis"],
        extraction_confidence_basis=value["extraction_confidence_basis"],
        entity_resolution_confidence_basis=value["entity_resolution_confidence_basis"],
        corroboration_strength=value["corroboration_strength"],
        resolution_state=ResolutionState(value["resolution_state"]),
        initiative_id=value.get("initiative_id"),
        supersedes_event_id=value.get("supersedes_event_id"),
        seller_relevance_state=SellerRelevanceState(
            value.get("seller_relevance_state", SellerRelevanceState.UNRESOLVED)
        ),
        markets=tuple(value.get("markets", ())),
        recency_state=value.get("recency_state", "UNKNOWN"),
        canonical_facility_id=value.get("canonical_facility_id"),
    )


def _provenance_from_payload(value: dict) -> Provenance:
    return Provenance(
        value["source_system"],
        value["source_record_id"],
        value.get("source_url"),
        _timestamp(value["observed_at"]),  # type: ignore[arg-type]
        _timestamp(value["recorded_at"]),  # type: ignore[arg-type]
        Classification(value["classification"]),
        EvidenceState(value["evidence_state"]),
        DataMode(value["data_mode"]),
        value["synthetic"],
        frozenset(SensitivityTag(item) for item in value.get("sensitivity_tags", ())),
        tuple(value.get("missing_fields", ())),
    )


def _organization_candidate_from_row(
    row: dict, promotion: dict | None = None
) -> OrganizationCandidate:
    return OrganizationCandidate(
        row["id"],
        row["identity_key"],
        row["source_name"],
        row["normalized_name"],
        tuple(tuple(item) for item in json.loads(row["source_identifiers"])),
        row["verified_domain"],
        row["canonical_industry"],
        _provenance_from_payload(json.loads(row["provenance"])),
        tuple(json.loads(row["event_ids"])),
        tuple(json.loads(row["observation_ids"])),
        ResolutionState(row["resolution_state"]),
        CandidateReviewState(row["review_state"]),
        row["resolution_reason"],
        tuple(json.loads(row["candidate_account_ids"])),
        _database_timestamp(row["created_at"]),
        _database_timestamp(row["observed_at"]),
        promotion["canonical_account_id"] if promotion else None,
        _database_timestamp(promotion["promoted_at"]) if promotion else None,
        _provenance_from_payload(json.loads(promotion["promotion_provenance"]))
        if promotion
        else None,
    )


def _program_candidate_from_row(
    row: dict, promotion: dict | None = None
) -> ProgramCandidate:
    return ProgramCandidate(
        row["id"],
        row["identity_key"],
        row["source_name"],
        row["organization_candidate_id"],
        row["canonical_account_id"],
        EventType(row["event_type"]),
        _provenance_from_payload(json.loads(row["provenance"])),
        tuple(json.loads(row["event_ids"])),
        ResolutionState(row["resolution_state"]),
        CandidateReviewState(row["review_state"]),
        _database_timestamp(row["created_at"]),
        _database_timestamp(row["observed_at"]),
        promotion["canonical_program_id"] if promotion else None,
        _database_timestamp(promotion["promoted_at"]) if promotion else None,
        _provenance_from_payload(json.loads(promotion["promotion_provenance"]))
        if promotion
        else None,
    )


class MonitorRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.research = MonitorResearchJournal(engine)

    @contextmanager
    def operational_lock(self):
        """Hold one cross-process PostgreSQL lock for a collection cycle."""
        if self.engine.dialect.name != "postgresql":
            yield True
            return
        with self.engine.connect() as connection:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(hashtext('btx-monitor-worker'))")
                ).scalar_one()
            )
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(
                        text(
                            "SELECT pg_advisory_unlock(hashtext('btx-monitor-worker'))"
                        )
                    )

    def persist_snapshot(
        self,
        *,
        run: CollectionRun,
        health: SourceHealth,
        observations: tuple[SourceObservation, ...],
        events: tuple[IntelligenceEvent, ...],
        clusters: tuple[EventCluster, ...],
        rejected: tuple[RejectedObservation, ...],
        organization_candidates: tuple[OrganizationCandidate, ...] = (),
        program_candidates: tuple[ProgramCandidate, ...] = (),
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(monitor_collection_runs).values(
                    id=run.id,
                    source_id=run.source_id,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    cursor=_json(run.cursor) if run.cursor else None,
                    records_seen=run.records_seen,
                    records_new=run.records_new,
                    records_changed=run.records_changed,
                    records_rejected=run.records_rejected,
                    events_created=run.events_created,
                    events_matched=run.events_matched,
                    failures=_json(run.failures),
                    latency_ms=run.latency_ms,
                    funnel=_json(run.funnel) if run.funnel is not None else None,
                )
            )
            connection.execute(
                delete(monitor_source_health).where(
                    monitor_source_health.c.source_id == health.source_id
                )
            )
            connection.execute(
                insert(monitor_source_health).values(
                    source_id=health.source_id,
                    state=health.state.value,
                    last_attempt_at=health.last_attempt_at,
                    last_success_at=health.last_success_at,
                    warning_code=health.warning_code,
                    detail=health.detail,
                    updated_at=run.completed_at or run.started_at,
                )
            )
            for observation in observations:
                connection.execute(
                    delete(monitor_observations).where(
                        monitor_observations.c.id == observation.id
                    )
                )
                connection.execute(
                    insert(monitor_observations).values(
                        id=observation.id,
                        source_id=observation.source_identity.source_system,
                        source_record_id=observation.source_identity.source_record_id,
                        source_version=observation.source_version.version_id,
                        content_hash=observation.source_version.content_hash,
                        canonical_url=observation.raw_evidence.locator,
                        published_at=observation.source_published_at,
                        retrieved_at=observation.observed_at,
                        source_tier=observation.source_tier,
                        collection_run_id=run.id,
                        payload_reference=observation.raw_payload_locator,
                        title=observation.title,
                        structured_payload=observation.structured_payload,
                        created_at=observation.observed_at,
                    )
                )
                version = observation.source_version
                connection.execute(
                    delete(monitor_source_versions).where(
                        monitor_source_versions.c.source_id
                        == observation.source_identity.source_system,
                        monitor_source_versions.c.source_record_id
                        == observation.source_identity.source_record_id,
                    )
                )
                connection.execute(
                    insert(monitor_source_versions).values(
                        source_id=observation.source_identity.source_system,
                        source_record_id=observation.source_identity.source_record_id,
                        version_id=version.version_id,
                        content_hash=version.content_hash,
                        first_seen_at=version.first_seen_at,
                        last_seen_at=version.last_seen_at,
                        changed_at=version.changed_at,
                        last_observation_id=observation.id,
                    )
                )
            for event in events:
                connection.execute(
                    delete(monitor_events).where(monitor_events.c.id == event.id)
                )
                observation = next(
                    item
                    for item in observations
                    if item.raw_evidence.id in {e.evidence_id for e in event.evidence}
                )
                connection.execute(
                    insert(monitor_events).values(
                        id=event.id,
                        source_id=observation.source_identity.source_system,
                        source_observation_id=observation.id,
                        event_type=event.event_type.value,
                        publication_date=observation.source_published_at,
                        collected_at=observation.observed_at,
                        updated_at=run.completed_at or observation.observed_at,
                        resolution_state=event.resolution_state.value,
                        seller_relevance_state=event.seller_relevance_state.value,
                        data_mode="LIVE_PUBLIC",
                        provenance_source_id=event.provenance.source_record_id,
                        provenance_url=event.provenance.source_url,
                        evidence_ids=_json(
                            tuple(item.evidence_id for item in event.evidence)
                        ),
                        event_payload=_json(event),
                    )
                )
            for cluster in clusters:
                connection.execute(
                    delete(monitor_event_clusters).where(
                        monitor_event_clusters.c.id == cluster.id
                    )
                )
                connection.execute(
                    insert(monitor_event_clusters).values(
                        id=cluster.id,
                        event_id=cluster.event_id,
                        observation_ids=_json(cluster.observation_ids),
                        evidence_ids=_json(cluster.evidence_ids),
                        related_event_ids=_json(cluster.related_event_ids),
                        ambiguity_reason=cluster.ambiguity_reason,
                    )
                )
            for item in rejected:
                identifier = f"{run.id}:{item.observation_id}"
                connection.execute(
                    delete(monitor_rejected_observations).where(
                        monitor_rejected_observations.c.id == identifier
                    )
                )
                connection.execute(
                    insert(monitor_rejected_observations).values(
                        id=identifier,
                        collection_run_id=run.id,
                        source_id=run.source_id,
                        observation_id=item.observation_id,
                        state=item.state.value,
                        reason=item.reason,
                        evidence_id=item.evidence_id,
                        rejected_at=item.rejected_at,
                    )
                )
            for item in organization_candidates:
                connection.execute(
                    delete(monitor_organization_candidates).where(
                        monitor_organization_candidates.c.id == item.id
                    )
                )
                connection.execute(
                    insert(monitor_organization_candidates).values(
                        id=item.id,
                        identity_key=item.identity_key,
                        source_name=item.source_name,
                        normalized_name=item.normalized_name,
                        source_identifiers=_json(item.source_identifiers),
                        verified_domain=item.verified_domain,
                        canonical_industry=item.canonical_industry,
                        provenance=_json(item.provenance),
                        event_ids=_json(item.event_ids),
                        observation_ids=_json(item.observation_ids),
                        resolution_state=item.resolution_state.value,
                        review_state=item.review_state.value,
                        resolution_reason=item.resolution_reason,
                        candidate_account_ids=_json(item.candidate_account_ids),
                        created_at=item.created_at,
                        observed_at=item.observed_at,
                        updated_at=run.completed_at or run.started_at,
                    )
                )
            for item in program_candidates:
                connection.execute(
                    delete(monitor_program_candidates).where(
                        monitor_program_candidates.c.id == item.id
                    )
                )
                connection.execute(
                    insert(monitor_program_candidates).values(
                        id=item.id,
                        identity_key=item.identity_key,
                        source_name=item.source_name,
                        organization_candidate_id=item.organization_candidate_id,
                        canonical_account_id=item.canonical_account_id,
                        event_type=item.event_type.value,
                        provenance=_json(item.provenance),
                        event_ids=_json(item.event_ids),
                        resolution_state=item.resolution_state.value,
                        review_state=item.review_state.value,
                        created_at=item.created_at,
                        observed_at=item.observed_at,
                        updated_at=run.completed_at or run.started_at,
                    )
                )

    def snapshot(self) -> dict[str, tuple[dict, ...]]:
        with self.engine.connect() as connection:
            return {
                "runs": tuple(
                    {
                        **dict(row),
                        "funnel": json.loads(row["funnel"]) if row["funnel"] else None,
                        "failures": json.loads(row["failures"]),
                        "cursor": json.loads(row["cursor"]) if row["cursor"] else None,
                    }
                    for row in connection.execute(
                        select(monitor_collection_runs)
                        .order_by(monitor_collection_runs.c.started_at.desc())
                        .limit(20)
                    ).mappings()
                ),
                "health": tuple(
                    dict(row)
                    for row in connection.execute(
                        select(monitor_source_health)
                    ).mappings()
                ),
                "events": tuple(
                    dict(row)
                    for row in connection.execute(
                        select(
                            monitor_events,
                            (
                                monitor_events.c.source_observation_id
                                == monitor_source_versions.c.last_observation_id
                            ).label("is_current_source_version"),
                        )
                        .outerjoin(
                            monitor_source_versions,
                            (
                                monitor_source_versions.c.source_id
                                == monitor_events.c.source_id
                            )
                            & (
                                monitor_source_versions.c.source_record_id
                                == monitor_events.c.provenance_source_id
                            ),
                        )
                        .order_by(monitor_events.c.updated_at.desc())
                        .limit(100)
                    ).mappings()
                ),
                "rejected": tuple(
                    dict(row)
                    for row in connection.execute(
                        select(monitor_rejected_observations)
                        .order_by(monitor_rejected_observations.c.rejected_at.desc())
                        .limit(20)
                    ).mappings()
                ),
                "intelligence_assessments": tuple(
                    {**dict(row), "projection": json.loads(row["projection"])}
                    for row in connection.execute(
                        select(monitor_intelligence_assessments)
                        .where(monitor_intelligence_assessments.c.is_current.is_(True))
                        .order_by(monitor_intelligence_assessments.c.created_at.desc())
                        .limit(100)
                    ).mappings()
                ),
            }

    def events(self) -> tuple[IntelligenceEvent, ...]:
        """Return durable canonical Monitor events as typed domain records."""
        return tuple(event for event, _observation in self.event_contexts())

    def event_contexts(
        self,
    ) -> tuple[tuple[IntelligenceEvent, SourceObservation | None], ...]:
        """One committed current-source snapshot for every public read consumer.

        Reconstitute only stored source fields, without rerunning identity or
        claiming missing original native identifiers/headers were retained.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    monitor_events.c.event_payload,
                    monitor_observations,
                    monitor_source_versions.c.first_seen_at.label("version_first_seen"),
                    monitor_source_versions.c.last_seen_at.label("version_last_seen"),
                    monitor_source_versions.c.changed_at.label("version_changed_at"),
                )
                .select_from(monitor_events)
                .outerjoin(
                    monitor_observations,
                    monitor_events.c.source_observation_id == monitor_observations.c.id,
                )
                .outerjoin(
                    monitor_source_versions,
                    (monitor_source_versions.c.source_id == monitor_events.c.source_id)
                    & (
                        monitor_source_versions.c.source_record_id
                        == monitor_events.c.provenance_source_id
                    ),
                )
                .where(
                    or_(
                        monitor_source_versions.c.last_observation_id.is_(None),
                        monitor_events.c.source_observation_id
                        == monitor_source_versions.c.last_observation_id,
                    )
                )
                .order_by(monitor_events.c.updated_at.desc())
            ).mappings()
            contexts = []
            for row in rows:
                event = _event_from_payload(row["event_payload"])
                if (
                    event.source_published_at is None
                    and row["published_at"] is not None
                ):
                    event = replace(
                        event,
                        source_published_at=_database_timestamp(row["published_at"]),
                    )
                primary = tuple(
                    item.evidence_id
                    for item in event.evidence
                    if item.role == "PRIMARY"
                )
                observation = None
                if (
                    row["id"] is not None
                    and len(primary) == 1
                    and row["version_first_seen"] is not None
                ):
                    identity = SourceIdentity(row["source_id"], row["source_record_id"])
                    version = SourceVersion(
                        row["source_record_id"],
                        row["source_version"],
                        row["content_hash"],
                        _database_timestamp(row["version_first_seen"]),
                        _database_timestamp(row["version_last_seen"]),
                        _database_timestamp(row["version_changed_at"])
                        if row["version_changed_at"]
                        else None,
                    )
                    retrieved = _database_timestamp(row["retrieved_at"])
                    observation = SourceObservation(
                        row["id"],
                        identity,
                        version,
                        retrieved,
                        row["title"] or "",
                        RawEvidenceReference(
                            primary[0],
                            identity,
                            version,
                            row["canonical_url"],
                            retrieved,
                        ),
                        _database_timestamp(row["published_at"])
                        if row["published_at"]
                        else None,
                        row["payload_reference"],
                        row["source_tier"],
                        row["collection_run_id"],
                        row["structured_payload"],
                    )
                contexts.append((event, observation))
            return tuple(contexts)

    def source_observation_payload(
        self, source_id: str, source_record_id: str
    ) -> str | None:
        """Current exact source assertion, for conservative failed-refresh retention."""
        with self.engine.connect() as connection:
            return connection.execute(
                select(monitor_observations.c.structured_payload)
                .join(
                    monitor_source_versions,
                    monitor_source_versions.c.last_observation_id
                    == monitor_observations.c.id,
                )
                .where(
                    monitor_source_versions.c.source_id == source_id,
                    monitor_source_versions.c.source_record_id == source_record_id,
                )
            ).scalar_one_or_none()

    def event_document(
        self, event_id: str, *, include_research: bool = False
    ) -> dict | None:
        """One exact event's persisted source; never a global evidence search."""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_observations, monitor_events.c.event_payload)
                    .join(
                        monitor_events,
                        monitor_events.c.source_observation_id
                        == monitor_observations.c.id,
                    )
                    .where(monitor_events.c.id == event_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        document = self._document_projection(row, event_id)
        if include_research:
            state = self.research.latest_for_source(event_id, document["content_hash"])
            document["research"] = (
                None
                if state is None
                else {
                    "run_id": state["id"],
                    "source_revision": state["source_revision"],
                    "status": state["status"],
                    "updated_at": state["updated_at"],
                    "attempt_count": state["attempt_count"],
                    "result": state["result"],
                    "steps": [
                        {
                            key: step[key]
                            for key in (
                                "number",
                                "tool",
                                "status",
                                "started_at",
                                "completed_at",
                            )
                        }
                        for step in state["steps"]
                    ],
                }
            )
        return document

    def collection_documents(
        self, run_ids: tuple[str, ...], *, limit: int
    ) -> tuple[dict, ...]:
        """Bounded current-cycle public research input, without scanning history."""
        if type(limit) is not int or not 0 <= limit <= 3 or len(run_ids) > 100:
            raise ValueError("Invalid collection research bounds.")
        if not run_ids or not limit:
            return ()
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        monitor_observations,
                        monitor_events.c.event_payload,
                        monitor_events.c.id.label("event_id"),
                    )
                    .join(
                        monitor_events,
                        monitor_events.c.source_observation_id
                        == monitor_observations.c.id,
                    )
                    .where(monitor_observations.c.collection_run_id.in_(run_ids))
                    .order_by(
                        case(
                            (monitor_events.c.resolution_state == "RESOLVED", 0),
                            else_=1,
                        ),
                        case(
                            (
                                monitor_events.c.seller_relevance_state
                                == "RESOLVED_ELIGIBLE",
                                0,
                            ),
                            else_=1,
                        ),
                        monitor_events.c.publication_date.desc().nullslast(),
                        monitor_events.c.id,
                    )
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return tuple(self._document_projection(row, row["event_id"]) for row in rows)

    def research_documents(
        self,
        run_ids: tuple[str, ...],
        *,
        limit: int,
        now: datetime,
        retained_days: int = 60,
    ) -> tuple[dict, ...]:
        """Rank current-cycle and retained relevant evidence for bounded research."""
        if type(limit) is not int or not 0 <= limit <= 3 or len(run_ids) > 100:
            raise ValueError("Invalid collection research bounds.")
        if not limit:
            return ()
        cutoff = now - timedelta(days=max(1, min(retained_days, 60)))
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        monitor_observations,
                        monitor_events.c.event_payload,
                        monitor_events.c.id.label("event_id"),
                    )
                    .join(
                        monitor_events,
                        monitor_events.c.source_observation_id
                        == monitor_observations.c.id,
                    )
                    .join(
                        monitor_source_versions,
                        monitor_source_versions.c.last_observation_id
                        == monitor_observations.c.id,
                    )
                    .where(
                        or_(
                            monitor_observations.c.collection_run_id.in_(run_ids),
                            monitor_events.c.publication_date >= cutoff,
                        )
                    )
                    .where(monitor_events.c.resolution_state == "RESOLVED")
                    .where(
                        monitor_events.c.seller_relevance_state.in_(
                            ("RESOLVED_ELIGIBLE", "RESOLVED_NEEDS_REVIEW")
                        )
                    )
                    .order_by(
                        case(
                            (
                                monitor_events.c.seller_relevance_state
                                == "RESOLVED_ELIGIBLE",
                                0,
                            ),
                            else_=1,
                        ),
                        monitor_events.c.publication_date.desc().nullslast(),
                        monitor_events.c.id,
                    )
                    .limit(500)
                )
                .mappings()
                .all()
            )
        candidates = []
        for row in rows:
            projected = self._document_projection(row, row["event_id"])
            prior = self.research.latest_for_source(
                projected["event_id"], projected["content_hash"]
            )
            if prior and prior.get("status") == "COMPLETED":
                continue
            document = projected.get("document") or {}
            passage_count = len(document.get("passages", ()))
            extraction_complete = bool(document.get("extraction_complete"))
            coverage_rank = (
                2
                if extraction_complete and passage_count
                else 1
                if passage_count
                else 0
            )
            pending_since = projected.get("retrieved_at") or projected.get(
                "published_at"
            )
            if pending_since and pending_since.tzinfo is None:
                pending_since = pending_since.replace(tzinfo=UTC)
            projected["pending_since"] = pending_since
            projected["queue_age_seconds"] = (
                max(0, int((now - pending_since).total_seconds()))
                if pending_since
                else None
            )
            candidates.append(
                (
                    0
                    if projected.get("seller_relevance_state") == "RESOLVED_ELIGIBLE"
                    else 1,
                    coverage_rank,
                    (
                        projected["published_at"].timestamp()
                        if projected.get("published_at")
                        else 0
                    ),
                    projected["event_id"],
                    projected,
                )
            )
        ordered = [item[-1] for item in sorted(candidates)]
        selected: list[dict] = []
        used_accounts: set[str] = set()
        used_sources: set[str] = set()
        for diversify in (True, False):
            for item in ordered:
                if item in selected:
                    continue
                account_ids = set(item.get("canonical_account_ids", ()))
                if diversify and (
                    item.get("source_id") in used_sources
                    or bool(account_ids & used_accounts)
                ):
                    continue
                selected.append(item)
                used_sources.add(str(item.get("source_id")))
                used_accounts.update(account_ids)
                if len(selected) == limit:
                    return tuple(selected)
        return tuple(selected)

    @staticmethod
    def _document_projection(row, event_id: str) -> dict:
        payload = json.loads(row["structured_payload"] or "{}")
        event = json.loads(row["event_payload"])
        return {
            "event_id": event_id,
            "observation_id": row["id"],
            "source_id": row["source_id"],
            "event_type": event.get("event_type"),
            "resolution_state": event.get("resolution_state"),
            "seller_relevance_state": event.get("seller_relevance_state"),
            "canonical_account_ids": sorted(
                {
                    item["canonical_account_id"]
                    for item in event["subject_entities"]
                    if item.get("canonical_account_id")
                }
            ),
            "source_record_id": row["source_record_id"],
            "content_hash": row["content_hash"],
            "source_url": row["canonical_url"],
            "title": row["title"],
            "published_at": row["published_at"],
            "retrieved_at": row["retrieved_at"],
            "collection_run_id": row["collection_run_id"],
            "document": payload.get("_retrieved_document"),
            "availability": "DOCUMENT_ATTEMPT_RECORDED"
            if "_retrieved_document" in payload
            else "NO_DOCUMENT_ATTEMPT_RECORDED",
        }

    def organization_candidate(self, identity_key: str) -> OrganizationCandidate | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_organization_candidates).where(
                        monitor_organization_candidates.c.identity_key == identity_key
                    )
                )
                .mappings()
                .one_or_none()
            )
            promotion = (
                connection.execute(
                    select(monitor_candidate_promotion_audits).where(
                        monitor_candidate_promotion_audits.c.candidate_id == row["id"]
                    )
                )
                .mappings()
                .one_or_none()
                if row
                else None
            )
        return (
            _organization_candidate_from_row(
                dict(row), dict(promotion) if promotion else None
            )
            if row
            else None
        )

    def organization_candidate_by_id(
        self, candidate_id: str
    ) -> OrganizationCandidate | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_organization_candidates).where(
                        monitor_organization_candidates.c.id == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            promotion = (
                connection.execute(
                    select(monitor_candidate_promotion_audits).where(
                        monitor_candidate_promotion_audits.c.candidate_id
                        == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
                if row
                else None
            )
        return (
            _organization_candidate_from_row(
                dict(row), dict(promotion) if promotion else None
            )
            if row
            else None
        )

    def program_candidate(self, identity_key: str) -> ProgramCandidate | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_program_candidates).where(
                        monitor_program_candidates.c.identity_key == identity_key
                    )
                )
                .mappings()
                .one_or_none()
            )
            promotion = (
                connection.execute(
                    select(monitor_program_candidate_promotion_audits).where(
                        monitor_program_candidate_promotion_audits.c.candidate_id
                        == row["id"]
                    )
                )
                .mappings()
                .one_or_none()
                if row
                else None
            )
        return (
            _program_candidate_from_row(
                dict(row), dict(promotion) if promotion else None
            )
            if row
            else None
        )

    def program_candidate_by_id(self, candidate_id: str) -> ProgramCandidate | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_program_candidates).where(
                        monitor_program_candidates.c.id == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            promotion = (
                connection.execute(
                    select(monitor_program_candidate_promotion_audits).where(
                        monitor_program_candidate_promotion_audits.c.candidate_id
                        == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
                if row
                else None
            )
        return (
            _program_candidate_from_row(
                dict(row), dict(promotion) if promotion else None
            )
            if row
            else None
        )

    def candidates(
        self,
    ) -> tuple[tuple[OrganizationCandidate, ...], tuple[ProgramCandidate, ...]]:
        with self.engine.connect() as connection:
            promotions = {
                row["candidate_id"]: dict(row)
                for row in connection.execute(
                    select(monitor_candidate_promotion_audits)
                ).mappings()
            }
            program_promotions = {
                row["candidate_id"]: dict(row)
                for row in connection.execute(
                    select(monitor_program_candidate_promotion_audits)
                ).mappings()
            }
            organizations = tuple(
                _organization_candidate_from_row(dict(row), promotions.get(row["id"]))
                for row in connection.execute(
                    select(monitor_organization_candidates).order_by(
                        monitor_organization_candidates.c.created_at
                    )
                ).mappings()
            )
            programs = tuple(
                _program_candidate_from_row(
                    dict(row), program_promotions.get(row["id"])
                )
                for row in connection.execute(
                    select(monitor_program_candidates).order_by(
                        monitor_program_candidates.c.created_at
                    )
                ).mappings()
            )
        return organizations, programs

    def source_content_hash(self, source_id: str, source_record_id: str) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(monitor_source_versions.c.content_hash).where(
                    monitor_source_versions.c.source_id == source_id,
                    monitor_source_versions.c.source_record_id == source_record_id,
                )
            ).scalar_one_or_none()

    def brief_synthesis(self, brief_id: str, governed_content_hash: str) -> dict | None:
        """Return only an exact governed-content match; stale prose never leaks."""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_brief_syntheses).where(
                        monitor_brief_syntheses.c.brief_id == brief_id,
                        monitor_brief_syntheses.c.governed_content_hash
                        == governed_content_hash,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        value = dict(row)
        if value.get("projection"):
            value["projection"] = json.loads(value["projection"])
        if value.get("next_retry_at"):
            value["next_retry_at"] = _database_timestamp(value["next_retry_at"])
        value["synthesized_at"] = _database_timestamp(value["synthesized_at"])
        return value

    @staticmethod
    def _assessment_context_key(
        event_id: str, account_id: str | None, business_unit_id: str | None
    ) -> str:
        return "|".join(
            (
                event_id,
                account_id or "UNRESOLVED",
                business_unit_id or "ALL_BUSINESS_UNITS",
            )
        )

    def intelligence_assessment(
        self,
        event_id: str,
        *,
        account_id: str | None,
        business_unit_id: str | None = None,
        input_revision: str | None = None,
    ) -> dict | None:
        context_key = self._assessment_context_key(
            event_id, account_id, business_unit_id
        )
        conditions = [
            monitor_intelligence_assessments.c.context_key == context_key,
            monitor_intelligence_assessments.c.is_current.is_(True),
        ]
        if input_revision:
            conditions.append(
                monitor_intelligence_assessments.c.input_revision == input_revision
            )
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_intelligence_assessments).where(*conditions)
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        value = dict(row)
        value["projection"] = json.loads(value["projection"])
        value["created_at"] = _database_timestamp(value["created_at"])
        return value

    def intelligence_assessment_history(
        self,
        event_id: str,
        *,
        account_id: str | None,
        business_unit_id: str | None = None,
    ) -> tuple[dict, ...]:
        context_key = self._assessment_context_key(
            event_id, account_id, business_unit_id
        )
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(monitor_intelligence_assessments)
                    .where(
                        monitor_intelligence_assessments.c.context_key == context_key
                    )
                    .order_by(monitor_intelligence_assessments.c.version.desc())
                )
                .mappings()
                .all()
            )
        return tuple(
            {
                **dict(row),
                "projection": json.loads(row["projection"]),
                "created_at": _database_timestamp(row["created_at"]),
            }
            for row in rows
        )

    def intelligence_assessment_by_id(self, assessment_id: str) -> dict | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_intelligence_assessments).where(
                        monitor_intelligence_assessments.c.id == assessment_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        return {
            **dict(row),
            "projection": json.loads(row["projection"]),
            "created_at": _database_timestamp(row["created_at"]),
        }

    def current_intelligence_assessments(
        self, *, limit: int = 1000
    ) -> tuple[dict, ...]:
        """Return a bounded newest-first index for seller read-window selection."""
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(monitor_intelligence_assessments)
                    .where(monitor_intelligence_assessments.c.is_current.is_(True))
                    .order_by(
                        monitor_intelligence_assessments.c.created_at.desc(),
                        monitor_intelligence_assessments.c.id,
                    )
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return tuple(
            {
                **dict(row),
                "projection": json.loads(row["projection"]),
                "created_at": _database_timestamp(row["created_at"]),
            }
            for row in rows
        )

    def save_intelligence_assessment(
        self,
        *,
        event_id: str,
        account_id: str | None,
        business_unit_id: str | None,
        input_revision: str,
        source_revision: str | None,
        projection: dict,
        generation_status: str,
        provider: str | None,
        model: str | None,
        created_at: datetime,
    ) -> dict:
        context_key = self._assessment_context_key(
            event_id, account_id, business_unit_id
        )
        serialized = json.dumps(projection, default=str, sort_keys=True)
        with self.engine.begin() as connection:
            current = (
                connection.execute(
                    select(monitor_intelligence_assessments).where(
                        monitor_intelligence_assessments.c.context_key == context_key,
                        monitor_intelligence_assessments.c.is_current.is_(True),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if current and current["input_revision"] == input_revision:
                if (
                    current["projection"] != serialized
                    or current["generation_status"] != generation_status
                ):
                    connection.execute(
                        update(monitor_intelligence_assessments)
                        .where(monitor_intelligence_assessments.c.id == current["id"])
                        .values(
                            projection=serialized,
                            generation_status=generation_status,
                            provider=provider,
                            model=model,
                        )
                    )
                version = int(current["version"])
                assessment_id = current["id"]
            else:
                version = int(current["version"]) + 1 if current else 1
                if current:
                    connection.execute(
                        update(monitor_intelligence_assessments)
                        .where(monitor_intelligence_assessments.c.id == current["id"])
                        .values(is_current=False)
                    )
                assessment_id = hashlib.sha256(
                    f"{context_key}|{version}|{input_revision}".encode()
                ).hexdigest()
                connection.execute(
                    insert(monitor_intelligence_assessments).values(
                        id=assessment_id,
                        context_key=context_key,
                        event_id=event_id,
                        account_id=account_id,
                        business_unit_id=business_unit_id,
                        input_revision=input_revision,
                        source_revision=source_revision,
                        version=version,
                        is_current=True,
                        projection=serialized,
                        generation_status=generation_status,
                        provider=provider,
                        model=model,
                        created_at=created_at,
                    )
                )
        return {
            "id": assessment_id,
            "version": version,
            "input_revision": input_revision,
            "generation_status": generation_status,
        }

    def save_brief_synthesis(
        self,
        *,
        brief_id: str,
        governed_content_hash: str,
        summary: str | None,
        provider: str | None,
        model: str | None,
        status: str,
        attempt_count: int,
        next_retry_at: datetime | None,
        synthesized_at: datetime,
        projection: dict | None = None,
        source_revision: str | None = None,
        input_revision: str | None = None,
    ) -> None:
        """Replace the one cached attempt for a brief with its current content hash."""
        with self.engine.begin() as connection:
            connection.execute(
                delete(monitor_brief_syntheses).where(
                    monitor_brief_syntheses.c.brief_id == brief_id
                )
            )
            connection.execute(
                insert(monitor_brief_syntheses).values(
                    brief_id=brief_id,
                    governed_content_hash=governed_content_hash,
                    summary=summary,
                    projection=json.dumps(projection, default=str, sort_keys=True)
                    if projection
                    else None,
                    source_revision=source_revision,
                    input_revision=input_revision,
                    provider=provider,
                    model=model,
                    status=status,
                    attempt_count=attempt_count,
                    next_retry_at=next_retry_at,
                    synthesized_at=synthesized_at,
                )
            )

    def brief_synthesis_count(self) -> int:
        with self.engine.connect() as connection:
            return len(
                connection.execute(select(monitor_brief_syntheses.c.brief_id)).all()
            )

    def technical_decomposition(
        self, event_id: str, governed_content_hash: str, account_id: str | None = None
    ) -> dict | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_technical_decompositions).where(
                        monitor_technical_decompositions.c.event_id == event_id,
                        monitor_technical_decompositions.c.account_id == account_id,
                        monitor_technical_decompositions.c.is_current.is_(True),
                        monitor_technical_decompositions.c.governed_content_hash
                        == governed_content_hash,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        value = dict(row)
        value["next_retry_at"] = (
            _database_timestamp(value["next_retry_at"])
            if value["next_retry_at"]
            else None
        )
        value["processed_at"] = _database_timestamp(value["processed_at"])
        return value

    def entity_candidate_resolution(self, cache_key: str) -> dict | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_entity_candidate_resolutions).where(
                        monitor_entity_candidate_resolutions.c.cache_key == cache_key
                    )
                )
                .mappings()
                .one_or_none()
            )
        return dict(row) if row else None

    def save_entity_candidate_resolution(
        self,
        *,
        cache_key: str,
        projection: dict,
        provider: str | None,
        model: str | None,
        status: str,
        processed_at: datetime,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(monitor_entity_candidate_resolutions).where(
                    monitor_entity_candidate_resolutions.c.cache_key == cache_key
                )
            )
            connection.execute(
                insert(monitor_entity_candidate_resolutions).values(
                    cache_key=cache_key,
                    projection=_json(projection),
                    provider=provider,
                    model=model,
                    status=status,
                    processed_at=processed_at,
                )
            )

    def technical_decomposition_for_event(
        self, event_id: str, account_id: str | None = None
    ) -> dict | None:
        """Read the worker-owned latest durable projection without reconstructing a provider model."""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_technical_decompositions)
                    .where(
                        monitor_technical_decompositions.c.event_id == event_id,
                        monitor_technical_decompositions.c.is_current.is_(True),
                        (monitor_technical_decompositions.c.account_id == account_id)
                        if account_id is not None
                        else true(),
                    )
                    .order_by(
                        monitor_technical_decompositions.c.account_id.is_(None),
                        monitor_technical_decompositions.c.version.desc(),
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        value = dict(row)
        value["next_retry_at"] = (
            _database_timestamp(value["next_retry_at"])
            if value["next_retry_at"]
            else None
        )
        value["processed_at"] = _database_timestamp(value["processed_at"])
        return value

    def save_technical_decomposition(
        self,
        *,
        event_id: str,
        governed_content_hash: str,
        projection: dict | None,
        provider: str | None,
        model: str | None,
        status: str,
        processed_at: datetime,
        attempt_count: int,
        next_retry_at: datetime | None,
        account_id: str | None = None,
        source_revision: str | None = None,
    ) -> None:
        context_key = f"{event_id}|{account_id or '*'}"
        serialized = _json(projection) if projection else None
        with self.engine.begin() as connection:
            current = (
                connection.execute(
                    select(monitor_technical_decompositions).where(
                        monitor_technical_decompositions.c.context_key == context_key,
                        monitor_technical_decompositions.c.is_current.is_(True),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if current and current["governed_content_hash"] == governed_content_hash:
                connection.execute(
                    update(monitor_technical_decompositions)
                    .where(monitor_technical_decompositions.c.id == current["id"])
                    .values(
                        projection=serialized,
                        provider=provider,
                        model=model,
                        status=status,
                        attempt_count=attempt_count,
                        next_retry_at=next_retry_at,
                        processed_at=processed_at,
                        source_revision=source_revision,
                    )
                )
                return
            version = int(current["version"]) + 1 if current else 1
            if current:
                connection.execute(
                    update(monitor_technical_decompositions)
                    .where(monitor_technical_decompositions.c.id == current["id"])
                    .values(is_current=False)
                )
            decomposition_id = hashlib.sha256(
                f"{context_key}|{version}|{governed_content_hash}".encode()
            ).hexdigest()
            connection.execute(
                insert(monitor_technical_decompositions).values(
                    id=decomposition_id,
                    context_key=context_key,
                    event_id=event_id,
                    account_id=account_id,
                    source_revision=source_revision,
                    governed_content_hash=governed_content_hash,
                    version=version,
                    is_current=True,
                    projection=serialized,
                    provider=provider,
                    model=model,
                    status=status,
                    attempt_count=attempt_count,
                    next_retry_at=next_retry_at,
                    processed_at=processed_at,
                )
            )

    def governed_explanation(
        self, subject_key: str, explanation_type: str, governed_content_hash: str
    ) -> dict | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(governed_explanations).where(
                        governed_explanations.c.subject_key == subject_key,
                        governed_explanations.c.explanation_type == explanation_type,
                        governed_explanations.c.governed_content_hash
                        == governed_content_hash,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if not row:
            return None
        value = dict(row)
        value["next_retry_at"] = (
            _database_timestamp(value["next_retry_at"])
            if value["next_retry_at"]
            else None
        )
        return value

    def latest_governed_explanation(
        self, subject_key: str, explanation_type: str
    ) -> dict | None:
        """Return the current seller-safe projection without reconstructing provider config."""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(governed_explanations)
                    .where(
                        governed_explanations.c.subject_key == subject_key,
                        governed_explanations.c.explanation_type == explanation_type,
                    )
                    .order_by(governed_explanations.c.processed_at.desc())
                )
                .mappings()
                .first()
            )
        if not row:
            return None
        value = dict(row)
        value["next_retry_at"] = (
            _database_timestamp(value["next_retry_at"])
            if value["next_retry_at"]
            else None
        )
        return value

    def latest_governed_explanations(
        self, subject_keys: tuple[str, ...], explanation_type: str
    ) -> dict[str, dict]:
        """Fetch seller-safe explanation records in one bounded database read."""
        keys = tuple(dict.fromkeys(subject_keys))
        if not keys:
            return {}
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(governed_explanations).where(
                        governed_explanations.c.subject_key.in_(keys),
                        governed_explanations.c.explanation_type == explanation_type,
                    )
                )
                .mappings()
                .all()
            )
        result = {}
        for row in rows:
            value = dict(row)
            value["next_retry_at"] = (
                _database_timestamp(value["next_retry_at"])
                if value["next_retry_at"]
                else None
            )
            result[value["subject_key"]] = value
        return result

    def save_governed_explanation(
        self,
        *,
        subject_key: str,
        explanation_type: str,
        governed_content_hash: str,
        projection: dict,
        provider: str | None,
        model: str | None,
        status: str,
        attempt_count: int,
        next_retry_at: datetime | None,
        processed_at: datetime,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(governed_explanations).where(
                    governed_explanations.c.subject_key == subject_key,
                    governed_explanations.c.explanation_type == explanation_type,
                )
            )
            connection.execute(
                insert(governed_explanations).values(
                    subject_key=subject_key,
                    explanation_type=explanation_type,
                    governed_content_hash=governed_content_hash,
                    projection=_json(projection),
                    provider=provider,
                    model=model,
                    status=status,
                    attempt_count=attempt_count,
                    next_retry_at=next_retry_at,
                    processed_at=processed_at,
                )
            )

    def cluster(self, cluster_id: str) -> EventCluster | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(monitor_event_clusters).where(
                        monitor_event_clusters.c.id == cluster_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return EventCluster(
            row["id"],
            row["event_id"],
            tuple(json.loads(row["observation_ids"])),
            tuple(json.loads(row["evidence_ids"])),
            tuple(json.loads(row["related_event_ids"])),
            row["ambiguity_reason"],
        )
