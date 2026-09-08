"""Separate deterministic decision families; models never supply their results.

Numerical defaults not specified by supplied decisions are provisional POC
configuration. Eligibility and coverage remain independent of weighted utility.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256

from btx_omni.modules.scoring.account_attractiveness import FACTORS

VERSION = "BTX_DECISION_FAMILIES_POC_1"


@dataclass(frozen=True)
class Family:
    key: str
    subject_kind: str
    weights: tuple[tuple[str, int], ...]
    minimum_coverage: Decimal = Decimal("0.70")
    interpretation: str = "Provisional deterministic POC index, not calibrated probability."


FAMILIES = {
    f.key: f for f in (
        Family("signal_confidence", "signal", (("source_reliability", 30), ("entity_match", 25), ("event_specificity", 20), ("independent_corroboration", 15), ("freshness", 10))),
        Family("opportunity_priority", "opportunity", tuple((f.key, int(f.weight * 100)) for f in FACTORS)),
        Family("pwin", "qualified_deal", (("buyer_commitment", 25), ("solution_fit", 20), ("commercial_position", 20), ("competitive_position", 20), ("decision_timing", 15)), Decimal(1), "Uncalibrated POC pursuit index; must not be displayed as a win probability."),
        Family("delivery_feasibility", "proposed_solution", (("qualification", 40), ("capacity", 30), ("materials", 20), ("logistics", 10)), Decimal(1)),
        Family("customer_health", "current_customer", (("commercial_momentum", 30), ("pipeline", 20), ("backlog", 15), ("engagement", 15), ("concentration", 10), ("friction", 10)), interpretation="POC longitudinal health uses separately derived health-oriented inputs, not opportunity scores."),
        Family("risk_severity", "public_risk_event", (("impact", 30), ("materiality", 20), ("imminence", 15), ("persistence", 15), ("breadth", 10), ("reversibility", 10))),
        Family("internal_commercial_risk", "current_customer", (("commercial_momentum", 30), ("pipeline", 20), ("backlog", 15), ("engagement", 15), ("concentration", 10), ("friction", 10))),
        Family("action_priority", "action", (("impact", 40), ("urgency", 30), ("readiness", 20), ("scope", 10))),
    )
}


@dataclass(frozen=True)
class FactorInput:
    points: Decimal | None
    evidence_ids: tuple[str, ...]
    reason: str
    raw_value: str | int | None = None
    period: str | None = None
    truth_class: str = "POC_SCENARIO"
    required_fields: tuple[str, ...] = ()
    observed_fields: tuple[str, ...] = ()

    def __post_init__(self):
        if self.points is not None and (not self.points.is_finite() or not Decimal(0) <= self.points <= Decimal(100)):
            raise ValueError("Factor points must be finite in [0, 100]")
        if self.points is not None and not self.evidence_ids:
            raise ValueError("A scored factor requires linked evidence")
        if not self.reason.strip():
            raise ValueError("A factor requires a seller-readable reason")
        if len(set(self.required_fields)) != len(self.required_fields) or len(set(self.observed_fields)) != len(self.observed_fields) or not set(self.observed_fields) <= set(self.required_fields):
            raise ValueError("Invalid factor field coverage contract")


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def assess(
    family_key: str, *, subject_id: str, as_of: str, revision: str,
    inputs: Mapping[str, FactorInput], eligible: bool,
    eligibility_reasons: tuple[str, ...] = (), blocking_constraints: tuple[str, ...] = (),
) -> dict:
    family = FAMILIES[family_key]
    expected = {name for name, _ in family.weights}
    if set(inputs) - expected:
        raise ValueError("Unknown factor cannot alter the governed rubric")
    if sum(weight for _, weight in family.weights) != 100:
        raise ValueError("Invalid family configuration")
    factors, missing, required_fields, observed_fields = [], [], [], []
    weighted_sum, known_weight = Decimal(0), 0
    for name, weight in family.weights:
        value = inputs.get(name)
        points = value.points if value else None
        required = value.required_fields if value and value.required_fields else (name,)
        observed = value.observed_fields if value and value.required_fields else (name,) if points is not None else ()
        required_fields.extend(f"{name}.{key}" for key in required)
        observed_fields.extend(f"{name}.{key}" for key in observed)
        if points is None:
            missing.append(name)
        else:
            known_weight += weight
            weighted_sum += points * weight
        factors.append({"key": name, "weight": weight, "points": points,
                        "contribution": _round(points * weight / 100) if points is not None else None,
                        "evidence_ids": value.evidence_ids if value else (),
                        "reason": value.reason if value else "Required evidence has not been established.",
                        "raw_value": value.raw_value if value else None,
                        "period": value.period if value else None,
                        "required_fields": required, "observed_fields": observed,
                        "truth_class": value.truth_class if value else None})
    factor_coverage = Decimal(len(expected) - len(missing)) / len(expected)
    coverage = Decimal(len(observed_fields)) / len(required_fields)
    usable = eligible and min(coverage, factor_coverage) >= family.minimum_coverage and not blocking_constraints
    score = _round(weighted_sum / known_weight) if usable and known_weight else None
    for factor in factors:
        factor["configured_contribution"] = factor["contribution"]
        factor["effective_weight_percent"] = _round(Decimal(factor["weight"]) * 100 / known_weight) if score is not None and factor["points"] is not None else None
        factor["contribution"] = _round(factor["points"] * factor["weight"] / known_weight) if score is not None and factor["points"] is not None else None
    return {
        "decision_id": "decision:" + sha256(repr((family, subject_id, as_of, revision, VERSION, sorted(inputs.items()), eligible, eligibility_reasons, blocking_constraints)).encode()).hexdigest()[:32],
        "family": family_key, "subject_kind": family.subject_kind, "subject_id": subject_id,
        "as_of": as_of, "revision": revision, "configuration_version": VERSION,
        "score": score, "score_unit": "POC_INDEX_0_TO_100", "provisional": True,
        "status": "BLOCKED" if blocking_constraints else "INELIGIBLE" if not eligible else "SCORED" if score is not None else "INSUFFICIENT_EVIDENCE",
        "eligible": eligible, "eligibility_reasons": eligibility_reasons,
        "blocking_constraints": blocking_constraints, "factors": factors,
        "data_coverage": {"family": "data_coverage", "subject_id": subject_id, "present": len(observed_fields), "applicable": len(required_fields), "ratio": coverage, "missing_fields": sorted(set(required_fields) - set(observed_fields)), "missing_factors": missing, "factor_coverage": factor_coverage},
        "interpretation": family.interpretation,
        "missingness_policy": "Fixed applicable denominator; partial scoring reweights known factor weights only above the declared coverage gate. Missing is never zero.",
    }


def public_risk_rollup(events: tuple[dict, ...]) -> dict:
    """Independent material domains, never article count, govern the uplift."""
    unique: dict[str, dict] = {}
    for event in events:
        if not event["active"]:
            continue
        score = Decimal(str(event["severity"]))
        if not score.is_finite() or not 0 <= score <= 100:
            raise ValueError("Invalid public risk severity")
        identity = event["underlying_event_id"]
        previous = unique.get(identity)
        if previous and (previous["severity"], previous["risk_domain"]) != (event["severity"], event["risk_domain"]):
            raise ValueError("Conflicting copies require event resolution before roll-up")
        unique[identity] = event
    if not unique:
        return {"score": None, "independent_event_ids": (), "uplift": 0}
    ranked = sorted(unique.values(), key=lambda e: (-Decimal(str(e["severity"])), e["underlying_event_id"]))
    material = [e for e in ranked if Decimal(str(e["severity"])) >= 40]
    domains = {e["risk_domain"] for e in material}
    severe_domains = {e["risk_domain"] for e in material if Decimal(str(e["severity"])) >= 70}
    uplift = 10 if len(domains) >= 3 or len(severe_domains) >= 2 else 5 if len(domains) >= 2 else 0
    return {"score": min(Decimal(100), Decimal(str(ranked[0]["severity"])) + uplift),
            "independent_event_ids": tuple(e["underlying_event_id"] for e in ranked),
            "uplift": uplift, "configuration_version": VERSION,
            "calibration": "Material>=40 and severe>=70 are provisional POC thresholds."}


def overall_customer_risk(*, current_customer: bool, internal_score: Decimal | None,
                          public_score: Decimal | None, public_confirmed: bool,
                          convergence_evidence_ids: tuple[str, ...] = (),
                          critical_override_evidence_ids: tuple[str, ...] = ()) -> dict:
    """Agreed 60/40 roll-up and non-dilution floors; no fabricated prospect risk."""
    for value in (internal_score, public_score):
        if value is not None and (not value.is_finite() or not 0 <= value <= 100):
            raise ValueError("Risk inputs must be valid governed indices")
    eligible = current_customer and internal_score is not None and public_score is not None
    missing = tuple(name for name, value in (("internal_commercial_risk", internal_score), ("public_risk_rollup", public_score)) if value is None)
    floors = []
    if public_confirmed and public_score is not None and public_score >= 85:
        floors.append(("CONFIRMED_PUBLIC_CRITICAL", Decimal(75)))
    if internal_score is not None and internal_score >= 85:
        floors.append(("INTERNAL_CRITICAL", Decimal(80)))
    if critical_override_evidence_ids:
        floors.append(("CONFIRMED_CRITICAL_OVERRIDE", Decimal(85)))
    uplift = 5 if eligible and internal_score >= 60 and public_score >= 60 and convergence_evidence_ids else 0
    raw = Decimal(".60") * internal_score + Decimal(".40") * public_score + uplift if eligible else None
    score = min(Decimal(100), max(raw, *(floor for _, floor in floors))) if eligible and floors else raw
    return {"family": "overall_customer_risk", "configuration_version": VERSION,
            "status": "INELIGIBLE" if not current_customer else "SCORED" if eligible else "INSUFFICIENT_EVIDENCE",
            "score": _round(score) if score is not None else None,
            "weights": {"internal_commercial_risk": 60, "public_risk_rollup": 40},
            "convergence_uplift": uplift, "convergence_evidence_ids": convergence_evidence_ids,
            "critical_override_evidence_ids": critical_override_evidence_ids,
            "applicable_floors": floors if current_customer else [], "missing_fields": missing,
            "interpretation": "Unknown coverage cannot create an overall score; independent critical conditions remain visible even when the combined index is unavailable."}


def customer_risk_projection(
    *,
    account_id: str,
    current_customer: bool,
    internal_decision: Mapping[str, object],
    signal_briefs: tuple[object, ...],
) -> dict:
    """Join current public risk and canonical internal risk without conflating them."""
    public_events: list[dict] = []
    confirmed_event_ids: list[str] = []
    for brief in sorted(signal_briefs, key=lambda item: str(getattr(item, "id", ""))):
        if account_id not in tuple(getattr(brief, "canonical_account_ids", ())):
            continue
        risk = getattr(brief, "risk_severity", None)
        if not isinstance(risk, Mapping) or risk.get("score") is None:
            continue
        active = (
            getattr(brief, "freshness", None) == "CURRENT"
            and getattr(brief, "seller_promotion_state", None) == "RESOLVED_ELIGIBLE"
        )
        event_id = str(brief.id)
        public_events.append(
            {
                "active": active,
                "severity": risk["score"],
                "underlying_event_id": event_id,
                "risk_domain": str(getattr(brief, "event_type", None) or "UNCLASSIFIED_RISK"),
            }
        )
        confidence = getattr(brief, "signal_confidence", None)
        if active and isinstance(confidence, Mapping) and confidence.get("status") == "SCORED":
            confirmed_event_ids.append(event_id)
    public = public_risk_rollup(tuple(public_events))
    internal_value = internal_decision.get("score")
    internal_score = Decimal(str(internal_value)) if internal_value is not None else None
    public_score = Decimal(str(public["score"])) if public["score"] is not None else None
    combined = overall_customer_risk(
        current_customer=current_customer,
        internal_score=internal_score,
        public_score=public_score,
        public_confirmed=bool(confirmed_event_ids),
    )
    return {
        "account_id": account_id,
        "public_risk_rollup": public,
        "overall_customer_risk": combined,
        "public_risk_events": tuple(public_events),
        "confirmed_public_event_ids": tuple(confirmed_event_ids),
        "interpretation": "Public event severity, internal commercial risk, and combined customer risk remain separate governed views.",
    }
