"""Bounded USAspending identity and seller-relevance policy.

The policy accepts a federal award as source evidence, never as BTX commercial
evidence.  A name that is merely similar to a researched account is not enough.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.contracts import (
    EntityResolution,
    IntelligenceEvent,
    RejectedObservation,
    SourceObservation,
)
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import (
    EventType,
    RejectionState,
    ResolutionState,
    SellerRelevanceState,
)
from btx_omni.monitor.policy import recency_state
from btx_omni.monitor.resolution import AccountWatchProfile

TARGET_INDUSTRIES = PRIMARY_MARKETS
ELIGIBLE_WINDOW_DAYS = 90
STALE_WINDOW_DAYS = 180
APPROVED_AWARD_TYPE_CODES = frozenset({"A", "B", "C", "D"})


def targeted_profiles(profiles: tuple[AccountWatchProfile, ...], *, rich_account_ids: set[str]) -> tuple[AccountWatchProfile, ...]:
    """Return only curated, in-scope public companies for bounded recipient queries."""
    return tuple(
        profile
        for profile in profiles
        if profile.canonical_account_id in rich_account_ids and TARGET_INDUSTRIES.intersection(profile.industries)
    )


def recipient_query_names(profiles: tuple[AccountWatchProfile, ...]) -> tuple[str, ...]:
    """Use only legal names or explicitly source-verified USAspending recipient names."""
    return tuple(sorted({name for profile in profiles for name in (profile.usaspending_recipient_names or (profile.legal_name,))}))


def _direct_evidence(observation: SourceObservation) -> bool:
    return bool(observation.raw_evidence.locator and observation.raw_evidence.locator != "https://api.usaspending.gov/api/v2/search/spending_by_award/")


def _normalize_legal_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _amount(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _recipient_resolution(mention: str, profiles: tuple[AccountWatchProfile, ...]) -> EntityResolution:
    normalized = _normalize_legal_name(mention)
    legal = [profile for profile in profiles if normalized == _normalize_legal_name(profile.legal_name) or normalized in {_normalize_legal_name(name) for name in profile.usaspending_recipient_names}]
    if len(legal) == 1:
        return EntityResolution(mention, legal[0].canonical_account_id, ResolutionState.RESOLVED, "usaspending_exact_recipient", "exact recipient name equals governed legal or source-verified recipient name")
    aliases = [profile for profile in profiles if normalized in {_normalize_legal_name(name) for name in (*profile.aliases, *profile.subsidiaries)}]
    candidates = tuple(profile.canonical_account_id for profile in (*legal, *aliases))
    if candidates:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "usaspending_alias_or_subsidiary", "parent, subsidiary, or alias is not an approved direct recipient mapping", candidates)
    return EntityResolution(mention, None, ResolutionState.UNRESOLVED, "usaspending_no_exact_recipient", "no exact governed recipient match")


def validate_usaspending_contract(observation: SourceObservation, payload: dict[str, object]) -> tuple[str, ...]:
    """Reject rows that cannot support a durable, directly inspectable award claim."""
    reasons: list[str] = []
    if not payload.get("generated_internal_id"):
        reasons.append("MISSING_STABLE_AWARD_IDENTIFIER")
    if not str(payload.get("Recipient Name") or "").strip():
        reasons.append("MISSING_RECIPIENT_NAME")
    if observation.source_published_at is None:
        reasons.append("MISSING_ACTION_DATE")
    if not _direct_evidence(observation):
        reasons.append("MISSING_DIRECT_OFFICIAL_EVIDENCE_URL")
    amount = _amount(payload.get("Award Amount"))
    if amount is None or amount <= 0:
        reasons.append("INVALID_OR_NON_POSITIVE_AWARD_AMOUNT")
    return tuple(reasons)


@dataclass(frozen=True)
class UsaSpendingDecision:
    event: IntelligenceEvent
    rejected: RejectedObservation | None = None


def normalize_usaspending_observation(
    observation: SourceObservation,
    *,
    profiles: tuple[AccountWatchProfile, ...],
    catalog: MonitorCatalog | None = None,
    now: datetime | None = None,
) -> UsaSpendingDecision:
    """Map one award without allowing broad federal-spending noise into seller views."""
    clock = now or datetime.now(UTC)
    payload = json.loads(observation.structured_payload or "{}")
    recipient = str(payload.get("Recipient Name") or "").strip()
    resolution = _recipient_resolution(recipient, profiles) if recipient else EntityResolution("missing recipient", None, ResolutionState.UNRESOLVED, "usaspending_recipient_missing", "source record has no recipient name")
    candidate = normalize_structured_observation(
        observation,
        subject_mention=recipient or None,
        event_type=EventType.CONTRACT_AWARD,
        catalog=catalog,
        source_markets=(),
        now=clock,
    )
    event = replace(
        candidate.event,
        subject_entities=(resolution,),
        resolution_state=resolution.state,
        recency_state=recency_state(observation.source_published_at, now=clock),
        markets=(catalog.markets_for_account(resolution.canonical_account_id) if catalog else candidate.event.markets),
    )
    action_date = observation.source_published_at
    award_code = str(payload.get("Award Type Code") or payload.get("Award Type") or "A").upper().strip()
    amount = _amount(payload.get("Award Amount"))
    description = str(payload.get("Description") or "").strip()
    contract_reasons = validate_usaspending_contract(observation, payload)
    reason: str | None = None
    state: SellerRelevanceState
    if contract_reasons:
        state, reason = SellerRelevanceState.REJECTED, "; ".join(contract_reasons)
    elif resolution.state is ResolutionState.AMBIGUOUS:
        state, reason = SellerRelevanceState.AMBIGUOUS, None
    elif resolution.state is ResolutionState.UNRESOLVED:
        state, reason = SellerRelevanceState.UNRESOLVED, None
    elif not description:
        state, reason = SellerRelevanceState.RESOLVED_NEEDS_REVIEW, None
    elif award_code not in APPROVED_AWARD_TYPE_CODES or amount <= 0:
        state, reason = SellerRelevanceState.REJECTED, "award is outside the approved material prime-award policy"
    elif clock - action_date > timedelta(days=STALE_WINDOW_DAYS):
        state, reason = SellerRelevanceState.REJECTED, "award action date is outside the USAspending stale window"
    elif clock - action_date > timedelta(days=ELIGIBLE_WINDOW_DAYS):
        state, reason = SellerRelevanceState.RESOLVED_NEEDS_REVIEW, None
    else:
        state, reason = SellerRelevanceState.RESOLVED_ELIGIBLE, None
    event = replace(event, seller_relevance_state=state, resolution_state=ResolutionState.REJECTED if state is SellerRelevanceState.REJECTED else resolution.state, amount=amount)
    rejected = None
    if reason:
        rejected_state = RejectionState.EXPIRED_EVENT if "stale" in reason else RejectionState.INSUFFICIENT_EVIDENCE if reason.startswith(("MISSING_", "INVALID_")) else RejectionState.NOT_RELEVANT
        rejected = RejectedObservation(observation.id, rejected_state, reason, observation.raw_evidence.id, clock)
    return UsaSpendingDecision(event, rejected)
