"""Durable Monitor state boundary; API routes never issue database queries directly."""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Engine, delete, insert, select, text

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
    RejectedObservation,
    SourceHealth,
    SourceObservation,
)
from btx_omni.monitor.ontology import (
    CandidateReviewState,
    EventType,
    ResolutionState,
    SellerRelevanceState,
)
from btx_omni.persistence.models import (
    monitor_brief_syntheses,
    monitor_candidate_promotion_audits,
    monitor_collection_runs,
    monitor_event_clusters,
    monitor_events,
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
    return json.dumps(asdict(value) if hasattr(value, "__dataclass_fields__") else value, default=encode, sort_keys=True)


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
            EventEvidence(item["evidence_id"], tuple(item["claim_predicates"]), item["role"])
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
            frozenset(SensitivityTag(item) for item in provenance.get("sensitivity_tags", ())),
            tuple(provenance.get("missing_fields", ())),
        ),
        source_confidence_basis=value["source_confidence_basis"],
        extraction_confidence_basis=value["extraction_confidence_basis"],
        entity_resolution_confidence_basis=value["entity_resolution_confidence_basis"],
        corroboration_strength=value["corroboration_strength"],
        resolution_state=ResolutionState(value["resolution_state"]),
        initiative_id=value.get("initiative_id"),
        supersedes_event_id=value.get("supersedes_event_id"),
        seller_relevance_state=SellerRelevanceState(value.get("seller_relevance_state", SellerRelevanceState.UNRESOLVED)),
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


def _organization_candidate_from_row(row: dict, promotion: dict | None = None) -> OrganizationCandidate:
    return OrganizationCandidate(
        row["id"], row["identity_key"], row["source_name"], row["normalized_name"],
        tuple(tuple(item) for item in json.loads(row["source_identifiers"])), row["verified_domain"], row["canonical_industry"],
        _provenance_from_payload(json.loads(row["provenance"])), tuple(json.loads(row["event_ids"])),
        tuple(json.loads(row["observation_ids"])), ResolutionState(row["resolution_state"]), CandidateReviewState(row["review_state"]),
        row["resolution_reason"], tuple(json.loads(row["candidate_account_ids"])), _database_timestamp(row["created_at"]), _database_timestamp(row["observed_at"]),
        promotion["canonical_account_id"] if promotion else None, _database_timestamp(promotion["promoted_at"]) if promotion else None,
        _provenance_from_payload(json.loads(promotion["promotion_provenance"])) if promotion else None,
    )


def _program_candidate_from_row(row: dict, promotion: dict | None = None) -> ProgramCandidate:
    return ProgramCandidate(
        row["id"], row["identity_key"], row["source_name"], row["organization_candidate_id"], row["canonical_account_id"],
        EventType(row["event_type"]), _provenance_from_payload(json.loads(row["provenance"])), tuple(json.loads(row["event_ids"])),
        ResolutionState(row["resolution_state"]), CandidateReviewState(row["review_state"]), _database_timestamp(row["created_at"]), _database_timestamp(row["observed_at"]),
        promotion["canonical_program_id"] if promotion else None, _database_timestamp(promotion["promoted_at"]) if promotion else None,
        _provenance_from_payload(json.loads(promotion["promotion_provenance"])) if promotion else None,
    )


class MonitorRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def operational_lock(self):
        """Hold one cross-process PostgreSQL lock for a collection cycle."""
        if self.engine.dialect.name != "postgresql":
            yield True
            return
        with self.engine.connect() as connection:
            acquired = bool(connection.execute(text("SELECT pg_try_advisory_lock(hashtext('btx-monitor-worker'))")).scalar_one())
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(hashtext('btx-monitor-worker'))"))

    def persist_snapshot(self, *, run: CollectionRun, health: SourceHealth, observations: tuple[SourceObservation, ...], events: tuple[IntelligenceEvent, ...], clusters: tuple[EventCluster, ...], rejected: tuple[RejectedObservation, ...], organization_candidates: tuple[OrganizationCandidate, ...] = (), program_candidates: tuple[ProgramCandidate, ...] = ()) -> None:
        with self.engine.begin() as connection:
            connection.execute(insert(monitor_collection_runs).values(id=run.id, source_id=run.source_id, started_at=run.started_at, completed_at=run.completed_at, cursor=_json(run.cursor) if run.cursor else None, records_seen=run.records_seen, records_new=run.records_new, records_changed=run.records_changed, records_rejected=run.records_rejected, events_created=run.events_created, events_matched=run.events_matched, failures=_json(run.failures), latency_ms=run.latency_ms))
            connection.execute(delete(monitor_source_health).where(monitor_source_health.c.source_id == health.source_id))
            connection.execute(insert(monitor_source_health).values(source_id=health.source_id, state=health.state.value, last_attempt_at=health.last_attempt_at, last_success_at=health.last_success_at, warning_code=health.warning_code, detail=health.detail, updated_at=run.completed_at or run.started_at))
            for observation in observations:
                connection.execute(delete(monitor_observations).where(monitor_observations.c.id == observation.id))
                connection.execute(insert(monitor_observations).values(id=observation.id, source_id=observation.source_identity.source_system, source_record_id=observation.source_identity.source_record_id, source_version=observation.source_version.version_id, content_hash=observation.source_version.content_hash, canonical_url=observation.raw_evidence.locator, published_at=observation.source_published_at, retrieved_at=observation.observed_at, source_tier=observation.source_tier, collection_run_id=run.id, payload_reference=observation.raw_payload_locator, title=observation.title, structured_payload=observation.structured_payload, created_at=observation.observed_at))
                version = observation.source_version
                connection.execute(delete(monitor_source_versions).where(monitor_source_versions.c.source_id == observation.source_identity.source_system, monitor_source_versions.c.source_record_id == observation.source_identity.source_record_id))
                connection.execute(insert(monitor_source_versions).values(source_id=observation.source_identity.source_system, source_record_id=observation.source_identity.source_record_id, version_id=version.version_id, content_hash=version.content_hash, first_seen_at=version.first_seen_at, last_seen_at=version.last_seen_at, changed_at=version.changed_at, last_observation_id=observation.id))
            for event in events:
                connection.execute(delete(monitor_events).where(monitor_events.c.id == event.id))
                observation = next(item for item in observations if item.raw_evidence.id in {e.evidence_id for e in event.evidence})
                connection.execute(insert(monitor_events).values(id=event.id, source_id=observation.source_identity.source_system, source_observation_id=observation.id, event_type=event.event_type.value, publication_date=event.event_date or observation.source_published_at, collected_at=observation.observed_at, updated_at=run.completed_at or observation.observed_at, resolution_state=event.resolution_state.value, seller_relevance_state=event.seller_relevance_state.value, data_mode="LIVE_PUBLIC", provenance_source_id=event.provenance.source_record_id, provenance_url=event.provenance.source_url, evidence_ids=_json(tuple(item.evidence_id for item in event.evidence)), event_payload=_json(event)))
            for cluster in clusters:
                connection.execute(delete(monitor_event_clusters).where(monitor_event_clusters.c.id == cluster.id))
                connection.execute(insert(monitor_event_clusters).values(id=cluster.id, event_id=cluster.event_id, observation_ids=_json(cluster.observation_ids), evidence_ids=_json(cluster.evidence_ids), related_event_ids=_json(cluster.related_event_ids), ambiguity_reason=cluster.ambiguity_reason))
            for item in rejected:
                identifier = f"{run.id}:{item.observation_id}"
                connection.execute(delete(monitor_rejected_observations).where(monitor_rejected_observations.c.id == identifier))
                connection.execute(insert(monitor_rejected_observations).values(id=identifier, collection_run_id=run.id, source_id=run.source_id, observation_id=item.observation_id, state=item.state.value, reason=item.reason, evidence_id=item.evidence_id, rejected_at=item.rejected_at))
            for item in organization_candidates:
                connection.execute(delete(monitor_organization_candidates).where(monitor_organization_candidates.c.id == item.id))
                connection.execute(insert(monitor_organization_candidates).values(id=item.id, identity_key=item.identity_key, source_name=item.source_name, normalized_name=item.normalized_name, source_identifiers=_json(item.source_identifiers), verified_domain=item.verified_domain, canonical_industry=item.canonical_industry, provenance=_json(item.provenance), event_ids=_json(item.event_ids), observation_ids=_json(item.observation_ids), resolution_state=item.resolution_state.value, review_state=item.review_state.value, resolution_reason=item.resolution_reason, candidate_account_ids=_json(item.candidate_account_ids), created_at=item.created_at, observed_at=item.observed_at, updated_at=run.completed_at or run.started_at))
            for item in program_candidates:
                connection.execute(delete(monitor_program_candidates).where(monitor_program_candidates.c.id == item.id))
                connection.execute(insert(monitor_program_candidates).values(id=item.id, identity_key=item.identity_key, source_name=item.source_name, organization_candidate_id=item.organization_candidate_id, canonical_account_id=item.canonical_account_id, event_type=item.event_type.value, provenance=_json(item.provenance), event_ids=_json(item.event_ids), resolution_state=item.resolution_state.value, review_state=item.review_state.value, created_at=item.created_at, observed_at=item.observed_at, updated_at=run.completed_at or run.started_at))

    def snapshot(self) -> dict[str, tuple[dict, ...]]:
        with self.engine.connect() as connection:
            return {
                "runs": tuple(dict(row) for row in connection.execute(select(monitor_collection_runs).order_by(monitor_collection_runs.c.started_at.desc()).limit(20)).mappings()),
                "health": tuple(dict(row) for row in connection.execute(select(monitor_source_health)).mappings()),
                "events": tuple(dict(row) for row in connection.execute(select(monitor_events).order_by(monitor_events.c.updated_at.desc()).limit(100)).mappings()),
                "rejected": tuple(dict(row) for row in connection.execute(select(monitor_rejected_observations).order_by(monitor_rejected_observations.c.rejected_at.desc()).limit(20)).mappings()),
            }

    def events(self) -> tuple[IntelligenceEvent, ...]:
        """Return durable canonical Monitor events as typed domain records."""
        with self.engine.connect() as connection:
            payloads = connection.execute(
                select(monitor_events.c.event_payload).order_by(monitor_events.c.updated_at.desc())
            ).scalars()
            return tuple(_event_from_payload(payload) for payload in payloads)

    def organization_candidate(self, identity_key: str) -> OrganizationCandidate | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(monitor_organization_candidates).where(monitor_organization_candidates.c.identity_key == identity_key)).mappings().one_or_none()
            promotion = connection.execute(select(monitor_candidate_promotion_audits).where(monitor_candidate_promotion_audits.c.candidate_id == row["id"])).mappings().one_or_none() if row else None
        return _organization_candidate_from_row(dict(row), dict(promotion) if promotion else None) if row else None

    def organization_candidate_by_id(self, candidate_id: str) -> OrganizationCandidate | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(monitor_organization_candidates).where(monitor_organization_candidates.c.id == candidate_id)).mappings().one_or_none()
            promotion = connection.execute(select(monitor_candidate_promotion_audits).where(monitor_candidate_promotion_audits.c.candidate_id == candidate_id)).mappings().one_or_none() if row else None
        return _organization_candidate_from_row(dict(row), dict(promotion) if promotion else None) if row else None

    def program_candidate(self, identity_key: str) -> ProgramCandidate | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(monitor_program_candidates).where(monitor_program_candidates.c.identity_key == identity_key)).mappings().one_or_none()
            promotion = connection.execute(select(monitor_program_candidate_promotion_audits).where(monitor_program_candidate_promotion_audits.c.candidate_id == row["id"])).mappings().one_or_none() if row else None
        return _program_candidate_from_row(dict(row), dict(promotion) if promotion else None) if row else None

    def program_candidate_by_id(self, candidate_id: str) -> ProgramCandidate | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(monitor_program_candidates).where(monitor_program_candidates.c.id == candidate_id)).mappings().one_or_none()
            promotion = connection.execute(select(monitor_program_candidate_promotion_audits).where(monitor_program_candidate_promotion_audits.c.candidate_id == candidate_id)).mappings().one_or_none() if row else None
        return _program_candidate_from_row(dict(row), dict(promotion) if promotion else None) if row else None

    def candidates(self) -> tuple[tuple[OrganizationCandidate, ...], tuple[ProgramCandidate, ...]]:
        with self.engine.connect() as connection:
            promotions = {row["candidate_id"]: dict(row) for row in connection.execute(select(monitor_candidate_promotion_audits)).mappings()}
            program_promotions = {row["candidate_id"]: dict(row) for row in connection.execute(select(monitor_program_candidate_promotion_audits)).mappings()}
            organizations = tuple(_organization_candidate_from_row(dict(row), promotions.get(row["id"])) for row in connection.execute(select(monitor_organization_candidates).order_by(monitor_organization_candidates.c.created_at)).mappings())
            programs = tuple(_program_candidate_from_row(dict(row), program_promotions.get(row["id"])) for row in connection.execute(select(monitor_program_candidates).order_by(monitor_program_candidates.c.created_at)).mappings())
        return organizations, programs

    def source_content_hash(self, source_id: str, source_record_id: str) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(monitor_source_versions.c.content_hash).where(
                    monitor_source_versions.c.source_id == source_id,
                    monitor_source_versions.c.source_record_id == source_record_id,
                )
            ).scalar_one_or_none()

    def brief_synthesis(
        self, brief_id: str, governed_content_hash: str
    ) -> dict | None:
        """Return only an exact governed-content match; stale prose never leaks."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(monitor_brief_syntheses).where(
                    monitor_brief_syntheses.c.brief_id == brief_id,
                    monitor_brief_syntheses.c.governed_content_hash
                    == governed_content_hash,
                )
            ).mappings().one_or_none()
        if not row:
            return None
        value = dict(row)
        if value.get("next_retry_at"):
            value["next_retry_at"] = _database_timestamp(value["next_retry_at"])
        value["synthesized_at"] = _database_timestamp(value["synthesized_at"])
        return value

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
            return len(connection.execute(select(monitor_brief_syntheses.c.brief_id)).all())

    def technical_decomposition(self, event_id: str, governed_content_hash: str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(monitor_technical_decompositions).where(
                monitor_technical_decompositions.c.event_id == event_id,
                monitor_technical_decompositions.c.governed_content_hash == governed_content_hash,
            )).mappings().one_or_none()
        return dict(row) if row else None

    def save_technical_decomposition(self, *, event_id: str, governed_content_hash: str, projection: dict | None, provider: str | None, model: str | None, status: str, processed_at: datetime) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(monitor_technical_decompositions).where(monitor_technical_decompositions.c.event_id == event_id))
            connection.execute(insert(monitor_technical_decompositions).values(event_id=event_id, governed_content_hash=governed_content_hash, projection=_json(projection) if projection else None, provider=provider, model=model, status=status, attempt_count=1, next_retry_at=None, processed_at=processed_at))

    def cluster(self, cluster_id: str) -> EventCluster | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(monitor_event_clusters).where(monitor_event_clusters.c.id == cluster_id)
            ).mappings().one_or_none()
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
