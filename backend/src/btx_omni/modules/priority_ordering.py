"""Source-neutral Today triage. No prose inference or blended Action Priority score."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PriorityMetadata(BaseModel):
    """Additive priority-item contract. Absent metadata is valid for older reads."""

    model_config = ConfigDict(extra="forbid")
    triage_class: int | None = Field(default=None, ge=0, le=3, strict=True)
    nature: Literal["RISK", "OPPORTUNITY", "UNKNOWN"] | None = None
    underlying_score: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    score_kind: (
        Literal[
            "OPPORTUNITY_PRIORITY",
            "RISK_SEVERITY",
            "CUSTOMER_HEALTH",
            "TIER_ONLY",
            "NONE",
        ]
        | None
    ) = None
    assessment_complete: bool | None = None
    high_importance: bool | None = None
    hard_stop: bool = False
    alert_kind: str | None = None
    status: str | None = None
    triage_reason: str | None = None


INTERNAL_NATURE = {
    "CUSTOMER_INACTIVITY": "RISK",
    "BOOKINGS_DECLINE": "RISK",
    "STALE_QUOTE": "RISK",
    "OVERDUE_ORDER": "RISK",
    "QUOTE_FOLLOW_UP": "OPPORTUNITY",
    "CRM_INACTIVITY": "OPPORTUNITY",
    "CROSS_BU_COORDINATION": "OPPORTUNITY",
    "INTELLIGENCE_COMMERCIAL_CONTEXT": "UNKNOWN",
}
PUBLIC_NATURE = {
    **dict.fromkeys(
        (
            "CONTRACT_REDUCTION",
            "PROGRAM_CANCELLATION",
            "FACILITY_CLOSURE",
            "WORKFORCE_REDUCTION",
            "FINANCIAL_DISTRESS",
            "EXPORT_RESTRICTION",
            "PRODUCTION_DELAY",
        ),
        "RISK",
    ),
    **dict.fromkeys(
        (
            "CONTRACT_AWARD",
            "SOLICITATION",
            "FACILITY_EXPANSION",
            "CAPACITY_EXPANSION",
            "NEW_FACILITY",
            "PROGRAM_LAUNCH",
            "PRODUCTION_RAMP",
            "PRODUCT_LAUNCH",
            "SUPPLIER_AWARD",
            "CAPITAL_INVESTMENT",
            "PARTNERSHIP",
            "REGULATORY_APPROVAL",
            "GOVERNMENT_FUNDING",
            "GRANT_AWARD",
        ),
        "OPPORTUNITY",
    ),
    **dict.fromkeys(
        (
            "UNCLASSIFIED_PUBLIC_UPDATE",
            "CONTRACT_MODIFICATION",
            "SUPPLY_CHAIN_CHANGE",
            "M_AND_A",
            "REGULATORY_CHANGE",
            "EXECUTIVE_CHANGE",
            "EARNINGS_SIGNAL",
            "BACKLOG_CHANGE",
        ),
        "UNKNOWN",
    ),
}
EXCLUDED = {
    "COMPLETED",
    "DONE",
    "DISMISSED",
    "HIDDEN",
    "SNOOZED",
    "DUPLICATE",
    "INVALID",
    "NO_LONGER_VALID",
    "CANCELED",
    "CANCELLED",
}
TIER_RANK = {"CRITICAL": 100, "HIGH": 75, "MEDIUM": 50, "MODERATE": 50, "LOW": 25}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return float(number) if number.is_finite() and 0 <= number <= 100 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _band(decision: dict) -> str | None:
    score = _number(decision.get("score"))
    if score is not None:
        return "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"
    # Explicitly incomplete numeric assessments cannot use a stale label to escalate.
    if decision.get("score_range") or decision.get("status") in {
        "PARTIAL_RANGE",
        "INSUFFICIENT_EVIDENCE",
        "INELIGIBLE",
        "BLOCKED",
    }:
        return None
    tier = str(decision.get("band") or decision.get("tier") or "").upper()
    return (
        "HIGH"
        if tier == "CRITICAL"
        else tier
        if tier in {"HIGH", "MEDIUM", "MODERATE", "LOW"}
        else None
    )


def _time(value: Any) -> float:
    if not value:
        return float("inf")
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.combine(value, datetime.min.time())
            if isinstance(value, date)
            else datetime.fromisoformat(str(value))
        )
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return float("inf")


@dataclass(frozen=True)
class PriorityCandidate:
    item: dict
    nature: str
    decision: dict
    score_kind: str
    confidence: dict
    missing: tuple
    hard_stop: bool
    excluded: bool
    identity: str
    due_date: Any
    created_at: Any


def priority_candidate(item: dict, source: Any) -> PriorityCandidate:
    """Read structured source fields only; source chooses an adapter, never order."""
    public = item["kind"] == "PUBLIC_SIGNAL"
    risk = getattr(source, "risk_severity", None)
    scores = (getattr(source, "evidence_package", None) or {}).get(
        "deterministic_scores"
    ) or {}
    if public:
        nature = (
            "RISK"
            if risk
            else PUBLIC_NATURE.get(getattr(source, "event_type", None), "UNKNOWN")
        )
        decision = (
            risk
            or (scores.get("opportunity_priority") if nature == "OPPORTUNITY" else None)
            or {}
        )
        score_kind = (
            "RISK_SEVERITY" if risk else "OPPORTUNITY_PRIORITY" if decision else "NONE"
        )
        confidence = getattr(source, "signal_confidence", None) or {}
    else:
        nature = INTERNAL_NATURE.get(item.get("alert_kind"), "UNKNOWN")
        risk = getattr(source, "risk_severity", None)
        opportunity = getattr(source, "opportunity_priority", None)
        health = getattr(source, "customer_health", None)
        decision = (
            (
                risk
                if nature == "RISK"
                else opportunity
                if nature == "OPPORTUNITY"
                else None
            )
            or health
            or {}
        )
        score_kind = (
            "RISK_SEVERITY"
            if decision is risk
            else "OPPORTUNITY_PRIORITY"
            if decision is opportunity
            else "CUSTOMER_HEALTH"
            if decision is health
            else "TIER_ONLY"
            if getattr(source, "severity", None)
            else "NONE"
        )
        if not decision:
            decision = {"band": getattr(source, "severity", None)}
        explicit_confidence = getattr(source, "evidence_confidence", None)
        if explicit_confidence is not None:
            confidence = (
                explicit_confidence
                if isinstance(explicit_confidence, dict)
                else {"band": explicit_confidence}
            )
        else:
            provenance = getattr(source, "provenance_state", None)
            confidence = (
                {"band": "HIGH"}
                if provenance == "CONFIRMED" and source.evidence_ids
                else {}
            )
    missing = (
        tuple(getattr(source, "missing_fields", ()) or ())
        + tuple((decision.get("data_coverage") or {}).get("missing_fields") or ())
        + tuple((confidence.get("data_coverage") or {}).get("missing_fields") or ())
    )
    status = str(getattr(source, "status", "")).upper()
    excluded = (
        status in EXCLUDED
        or getattr(source, "valid", True) is False
        or any(
            getattr(source, flag, False) is True
            for flag in ("completed", "dismissed", "hidden", "snoozed", "duplicate")
        )
    )
    return PriorityCandidate(
        item,
        nature,
        decision,
        score_kind,
        confidence,
        missing,
        getattr(source, "hard_stop", False) is True,
        excluded,
        str(getattr(source, "deduplication_key", None) or item["id"]),
        getattr(source, "due_date", None),
        getattr(source, "created_at", None) or item.get("observed_at"),
    )


def _assess(candidate: PriorityCandidate) -> tuple[PriorityMetadata, tuple]:
    decision = candidate.decision
    score = _number(decision.get("score"))
    ceiling = _number((decision.get("score_range") or {}).get("high"))
    band = _band(decision)
    confidence = _band(candidate.confidence)
    complete = bool(
        candidate.nature != "UNKNOWN"
        and confidence
        and not candidate.missing
        and (score is not None or band)
        and decision.get("status")
        not in {"PARTIAL_RANGE", "INSUFFICIENT_EVIDENCE", "INELIGIBLE", "BLOCKED"}
    )
    high_risk = (
        candidate.nature == "RISK"
        and candidate.score_kind != "CUSTOMER_HEALTH"
        and band == "HIGH"
    )
    if candidate.hard_stop:
        triage, reason = (
            0,
            "Explicit confirmed safety, legal, or stopped-shipment condition",
        )
    elif high_risk and confidence == "HIGH":
        triage, reason = (
            1,
            "Escalate now: risk rated High with High evidence confidence",
        )
    elif high_risk and confidence in {"MEDIUM", "MODERATE", "LOW"}:
        triage, reason = (
            2,
            "Validate immediately: risk rated High with Medium or Low evidence confidence",
        )
    elif candidate.nature == "UNKNOWN":
        triage, reason = 3, "Risk or opportunity nature is unknown"
    elif confidence is None:
        triage, reason = 3, "Evidence confidence is unknown"
    else:
        triage, reason = (
            3,
            "Other executable item ordered by assessment and underlying score",
        )
    # A range ceiling affects ordering only. It is not a confirmed top-band score.
    high = (
        triage < 3
        or high_risk
        or (
            candidate.nature == "OPPORTUNITY"
            and candidate.score_kind == "OPPORTUNITY_PRIORITY"
            and score is not None
            and score >= 75
        )
    )
    score_kind = candidate.score_kind
    underlying = score if complete else ceiling if ceiling is not None else score
    if underlying is None and band:
        score_kind = "TIER_ONLY"
    metadata = PriorityMetadata(
        triage_class=triage,
        nature=candidate.nature,
        underlying_score=underlying,
        score_kind=score_kind,
        assessment_complete=complete,
        high_importance=high,
        hard_stop=candidate.hard_stop,
        triage_reason=reason,
    )
    # Tier rank is an ordinal fallback, never presented as a measured score.
    tier = str(decision.get("band") or decision.get("tier") or "").upper()
    tier_rank = TIER_RANK.get(tier, TIER_RANK.get(band, -1)) if band else -1
    ordering_score = underlying if underlying is not None else tier_rank
    key = (
        triage,
        not complete,
        -ordering_score,
        _time(candidate.due_date),
        _time(candidate.created_at),
        candidate.item["id"],
    )
    return metadata, key


def order_priorities(candidates: list[PriorityCandidate]) -> tuple[dict, ...]:
    """Exclude closed identities, deduplicate and emit additive metadata in order."""
    closed = {candidate.identity for candidate in candidates if candidate.excluded}
    assessed = [
        (candidate, *_assess(candidate))
        for candidate in candidates
        if candidate.identity not in closed
    ]
    seen: set[str] = set()
    result = []
    for candidate, metadata, _ in sorted(assessed, key=lambda row: row[2]):
        if candidate.identity in seen:
            continue
        seen.add(candidate.identity)
        result.append({**candidate.item, **metadata.model_dump(exclude_unset=True)})
    return tuple(result)
