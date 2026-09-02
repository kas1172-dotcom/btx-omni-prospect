"""Framework-neutral Monitor contracts. Confidence fields name their evidence basis."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import require_aware
from btx_omni.monitor.ontology import (
    CandidateReviewState,
    EventType,
    RejectionState,
    ResolutionState,
    SellerRelevanceState,
    SourceHealthState,
)


@dataclass(frozen=True)
class SourceIdentity:
    source_system: str
    source_record_id: str
    source_native_ids: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SourceVersion:
    source_record_id: str
    version_id: str | None
    content_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    changed_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.first_seen_at, "first_seen_at")
        require_aware(self.last_seen_at, "last_seen_at")
        if self.changed_at is not None:
            require_aware(self.changed_at, "changed_at")


@dataclass(frozen=True)
class RawEvidenceReference:
    id: str
    source_identity: SourceIdentity
    source_version: SourceVersion
    locator: str
    captured_at: datetime
    excerpt: str | None = None
    media_type: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.captured_at, "captured_at")


@dataclass(frozen=True)
class SourceObservation:
    id: str
    source_identity: SourceIdentity
    source_version: SourceVersion
    observed_at: datetime
    title: str
    raw_evidence: RawEvidenceReference
    source_published_at: datetime | None = None
    raw_payload_locator: str | None = None
    source_tier: str = "TIER_1_AUTHORITATIVE_STRUCTURED"
    collection_run_id: str | None = None
    structured_payload: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "observed_at")
        if self.source_published_at is not None:
            require_aware(self.source_published_at, "source_published_at")


@dataclass(frozen=True)
class NormalizedClaim:
    predicate: str
    value: str
    evidence_ids: tuple[str, ...]
    extraction_method: str
    extraction_confidence: str


@dataclass(frozen=True)
class EventEvidence:
    evidence_id: str
    claim_predicates: tuple[str, ...]
    role: str


@dataclass(frozen=True)
class EntityResolution:
    mention: str
    canonical_account_id: str | None
    state: ResolutionState
    method: str
    confidence_basis: str
    candidate_account_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgramResolution:
    mention: str | None
    canonical_program_id: str | None
    state: ResolutionState
    method: str
    confidence_basis: str


@dataclass(frozen=True)
class IntelligenceEvent:
    id: str
    event_type: EventType
    subject_entities: tuple[EntityResolution, ...]
    related_entities: tuple[EntityResolution, ...]
    program: ProgramResolution
    geography: str | None
    event_date: datetime | None
    amount: Decimal | None
    currency: str | None
    claims: tuple[NormalizedClaim, ...]
    evidence: tuple[EventEvidence, ...]
    provenance: Provenance
    source_confidence_basis: str
    extraction_confidence_basis: str
    entity_resolution_confidence_basis: str
    corroboration_strength: str
    resolution_state: ResolutionState
    initiative_id: str | None = None
    supersedes_event_id: str | None = None
    seller_relevance_state: SellerRelevanceState = SellerRelevanceState.UNRESOLVED
    markets: tuple[str, ...] = ()
    recency_state: str = "UNKNOWN"
    canonical_facility_id: str | None = None

    def __post_init__(self) -> None:
        if self.event_date is not None:
            require_aware(self.event_date, "event_date")
        if not self.evidence:
            raise ValueError("intelligence events require evidence lineage")


@dataclass(frozen=True)
class EventCluster:
    id: str
    event_id: str
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    related_event_ids: tuple[str, ...] = ()
    ambiguity_reason: str | None = None


@dataclass(frozen=True)
class InitiativeLink:
    initiative_id: str
    event_id: str
    relationship: str


@dataclass(frozen=True)
class CollectionCursor:
    source_id: str
    token: str | None = None
    page: int | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class CollectionRun:
    id: str
    source_id: str
    started_at: datetime
    completed_at: datetime | None
    cursor: CollectionCursor | None
    records_seen: int = 0
    records_new: int = 0
    records_changed: int = 0
    records_rejected: int = 0
    events_created: int = 0
    events_matched: int = 0
    failures: tuple[str, ...] = ()
    latency_ms: int | None = None


@dataclass(frozen=True)
class SourceHealth:
    source_id: str
    state: SourceHealthState
    last_attempt_at: datetime
    last_success_at: datetime | None
    warning_code: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SourceOperationalStatus:
    source_id: str
    source_name: str
    state: SourceHealthState
    collectable: bool
    content_structure: str
    credential_requirement: str
    targeting_inputs: tuple[str, ...]
    freshness_threshold_hours: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    failure_summary: str | None
    durable_state: bool
    records_seen: int
    events_created: int
    seller_promotion_permitted: bool


@dataclass(frozen=True)
class RejectedObservation:
    observation_id: str
    state: RejectionState
    reason: str
    evidence_id: str
    rejected_at: datetime


@dataclass(frozen=True)
class OrganizationCandidate:
    """A source-backed public organization that is not a canonical Account."""

    id: str
    identity_key: str
    source_name: str
    normalized_name: str
    source_identifiers: tuple[tuple[str, str], ...]
    verified_domain: str | None
    canonical_industry: str | None
    provenance: Provenance
    event_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    resolution_state: ResolutionState
    review_state: CandidateReviewState
    resolution_reason: str
    candidate_account_ids: tuple[str, ...]
    created_at: datetime
    observed_at: datetime
    promoted_account_id: str | None = None
    promoted_at: datetime | None = None
    promotion_provenance: Provenance | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.observed_at, "observed_at")
        if self.promoted_at is not None:
            require_aware(self.promoted_at, "promoted_at")


@dataclass(frozen=True)
class ProgramCandidate:
    """Explicit public program evidence that is not yet a canonical Program."""

    id: str
    identity_key: str
    source_name: str
    organization_candidate_id: str | None
    canonical_account_id: str | None
    event_type: EventType
    provenance: Provenance
    event_ids: tuple[str, ...]
    resolution_state: ResolutionState
    review_state: CandidateReviewState
    created_at: datetime
    observed_at: datetime
    promoted_program_id: str | None = None
    promoted_at: datetime | None = None
    promotion_provenance: Provenance | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.observed_at, "observed_at")
        if self.promoted_at is not None:
            require_aware(self.promoted_at, "promoted_at")
