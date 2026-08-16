"""Canonical exact-first deterministic commercial matching; no semantic matching."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState, MatchState


class MatchReviewState(StrEnum):
    UNAMBIGUOUS = "UNAMBIGUOUS"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class CommercialComponent:
    id: str
    account_id: str | None
    program_id: str | None
    raw_part_reference: str | None
    component_class: str | None
    material: str | None
    process: str | None
    part_family: str | None
    evidence_state: EvidenceState
    evidence_ids: tuple[str, ...]
    provenance: Provenance
    capability_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalQuoteContext:
    quote_id: str
    account_id: str
    business_unit: str
    raw_part_reference: str | None
    component_class: str | None
    material: str | None
    process: str | None
    part_family: str | None
    evidence_ids: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True)
class CommercialMatch:
    component_id: str
    quote_id: str | None
    account_id: str | None
    method: MatchState
    review_state: MatchReviewState
    matched_attributes: tuple[str, ...]
    conflicting_attributes: tuple[str, ...]
    missing_attributes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_state: EvidenceState
    business_unit: str | None
    capability_ids: tuple[str, ...]


def normalize_part_reference(value: str | None) -> str | None:
    return None if value is None or not value.strip() else "".join(value.upper().split())


def match_component_to_quote(component: CommercialComponent, quote: HistoricalQuoteContext | None) -> CommercialMatch:
    if quote is None:
        return CommercialMatch(component.id, None, component.account_id, MatchState.INSUFFICIENT_DATA, MatchReviewState.AMBIGUOUS, (), (), ("historical_quote",), component.evidence_ids, component.evidence_state, None, ())
    evidence = tuple(dict.fromkeys(component.evidence_ids + quote.evidence_ids))
    left, right = normalize_part_reference(component.raw_part_reference), normalize_part_reference(quote.raw_part_reference)
    if left and right:
        if left == right:
            return CommercialMatch(component.id, quote.quote_id, quote.account_id, MatchState.EXACT_PART, MatchReviewState.UNAMBIGUOUS, ("part_reference",), (), (), evidence, component.evidence_state, quote.business_unit, component.capability_ids)
        return CommercialMatch(component.id, quote.quote_id, quote.account_id, MatchState.NO_MATCH, MatchReviewState.CONFLICT, (), ("part_reference",), (), evidence, component.evidence_state, quote.business_unit, ())
    matched: list[str] = []
    conflicts: list[str] = []
    missing: list[str] = []
    for name in ("component_class", "material", "process", "part_family"):
        lhs, rhs = getattr(component, name), getattr(quote, name)
        if not lhs or not rhs:
            missing.append(name)
        elif lhs.casefold() == rhs.casefold():
            matched.append(name)
        else:
            conflicts.append(name)
    if conflicts:
        method, review = MatchState.NO_MATCH, MatchReviewState.CONFLICT
    elif len(matched) >= 2:
        method, review = MatchState.STRUCTURED_SIMILARITY, MatchReviewState.UNAMBIGUOUS
    elif matched:
        method, review = MatchState.INSUFFICIENT_DATA, MatchReviewState.AMBIGUOUS
    else:
        method, review = MatchState.INSUFFICIENT_DATA, MatchReviewState.AMBIGUOUS
    return CommercialMatch(component.id, quote.quote_id, quote.account_id, method, review, tuple(matched), tuple(conflicts), tuple(missing), evidence, component.evidence_state, quote.business_unit, component.capability_ids if method is MatchState.STRUCTURED_SIMILARITY else ())
