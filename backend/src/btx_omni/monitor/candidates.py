"""Deterministic Monitor candidate construction; never creates canonical Accounts."""
from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

from btx_omni.monitor.contracts import (
    IntelligenceEvent,
    OrganizationCandidate,
    ProgramCandidate,
    SourceObservation,
)
from btx_omni.monitor.ontology import (
    CandidateReviewState,
    ResolutionState,
    SellerRelevanceState,
)

_IDENTIFIER_KINDS = frozenset({"cage", "cik", "domain", "official_domain", "uei"})
_PROGRAM_FIELDS = ("Program Name", "program_name", "program", "program_title")
_UNUSABLE_MENTIONS = frozenset({"", "missing recipient", "unresolved source subject"})


def normalized_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def explicit_program_mention(observation: SourceObservation) -> str | None:
    try:
        payload = json.loads(observation.structured_payload or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return next(
        (
            str(payload[field]).strip()
            for field in _PROGRAM_FIELDS
            if str(payload.get(field) or "").strip()
        ),
        None,
    )


def _authoritative_identifiers(observation: SourceObservation) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (kind.casefold(), value.strip())
            for kind, value in observation.source_identity.source_native_ids
            if kind.casefold() in _IDENTIFIER_KINDS and value.strip()
        )
    )


def _identity_key(*, source_name: str, observation: SourceObservation) -> str:
    identifiers = _authoritative_identifiers(observation)
    if identifiers:
        return "identifier:" + "|".join(f"{kind}={value.casefold()}" for kind, value in identifiers)
    return f"source-name:{observation.source_identity.source_system}:{normalized_name(source_name)}"


def _stable_id(prefix: str, identity_key: str) -> str:
    return f"{prefix}-{sha256(identity_key.encode()).hexdigest()[:24]}"


def _review_state(event: IntelligenceEvent) -> CandidateReviewState:
    if event.resolution_state is ResolutionState.AMBIGUOUS:
        return CandidateReviewState.AMBIGUOUS
    if event.resolution_state is ResolutionState.REJECTED or event.seller_relevance_state is SellerRelevanceState.REJECTED:
        return CandidateReviewState.REJECTED
    # Promotion requirements have not been approved. Exact public identity
    # evidence is reviewable, never auto-promotion-ready.
    return CandidateReviewState.PENDING_REVIEW


def organization_candidate_for(
    event: IntelligenceEvent,
    observation: SourceObservation,
    *,
    existing: OrganizationCandidate | None = None,
) -> OrganizationCandidate | None:
    subject = event.subject_entities[0] if event.subject_entities else None
    if subject is None or subject.state is ResolutionState.RESOLVED:
        return None
    source_name = subject.mention.strip()
    if source_name.casefold() in _UNUSABLE_MENTIONS:
        return None
    identity_key = _identity_key(source_name=source_name, observation=observation)
    current = OrganizationCandidate(
        _stable_id("organization-candidate", identity_key),
        identity_key,
        source_name,
        normalized_name(source_name),
        _authoritative_identifiers(observation),
        None,
        event.markets[0] if len(event.markets) == 1 else None,
        event.provenance,
        (event.id,),
        (observation.id,),
        event.resolution_state,
        _review_state(event),
        subject.confidence_basis,
        subject.candidate_account_ids,
        observation.observed_at,
        observation.observed_at,
    )
    if existing is None:
        return current
    return replace(
        current,
        id=existing.id,
        event_ids=tuple(dict.fromkeys((*existing.event_ids, event.id))),
        observation_ids=tuple(dict.fromkeys((*existing.observation_ids, observation.id))),
        created_at=existing.created_at,
        observed_at=max(existing.observed_at, observation.observed_at),
    )


def program_candidate_for(
    event: IntelligenceEvent,
    observation: SourceObservation,
    *,
    organization_candidate: OrganizationCandidate | None,
    existing: ProgramCandidate | None = None,
) -> ProgramCandidate | None:
    # A canonical Program always wins. Only a source-supplied, unresolved
    # program name is candidate material; a company mention alone is not.
    if event.program.canonical_program_id or event.program.state is not ResolutionState.UNRESOLVED:
        return None
    source_name = event.program.mention
    if not source_name:
        return None
    owner = organization_candidate.id if organization_candidate else event.subject_entities[0].canonical_account_id if event.subject_entities else None
    identity_key = f"program:{owner or 'unassigned'}:{observation.source_identity.source_system}:{normalized_name(source_name)}"
    current = ProgramCandidate(
        _stable_id("program-candidate", identity_key),
        identity_key,
        source_name,
        organization_candidate.id if organization_candidate else None,
        event.subject_entities[0].canonical_account_id if event.subject_entities else None,
        event.event_type,
        event.provenance,
        (event.id,),
        event.program.state,
        CandidateReviewState.PENDING_REVIEW,
        observation.observed_at,
        observation.observed_at,
    )
    if existing is None:
        return current
    return replace(
        current,
        id=existing.id,
        event_ids=tuple(dict.fromkeys((*existing.event_ids, event.id))),
        created_at=existing.created_at,
        observed_at=max(existing.observed_at, observation.observed_at),
    )
