"""Deterministic Prospect Fit v2 projection from explicit canonical evidence.

Missing factors are not reweighted. The seller sees the bounded low/high result
required by the approved rubric until every applicable factor is known.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from btx_omni.domain.markets import PRIMARY_MARKET_ORDER

CONFIGURATION_VERSION = "prospect-fit-v2.0"


@dataclass(frozen=True)
class ProspectFitFactor:
    key: str
    label: str
    weight: Decimal
    points: Decimal | None
    reason: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProspectFitProjection:
    applicable: bool
    score: Decimal | None
    score_low: Decimal | None
    score_high: Decimal | None
    coverage: Decimal
    status: str
    configuration_version: str
    factors: tuple[ProspectFitFactor, ...]
    missingness: tuple[str, ...]


_DEFINITIONS = (
    ("target_cohort_match", "Target-cohort match", Decimal(30)),
    ("manufacturing_fit", "Manufacturing fit", Decimal(25)),
    ("scale", "Scale", Decimal(15)),
    ("outsourcing_posture", "Outsourcing posture", Decimal(15)),
    ("strategic_archetype", "Strategic archetype", Decimal(10)),
    ("existing_btx_access", "Existing BTX access", Decimal(5)),
)


def prospect_fit_projection(account, *, applicable: bool) -> ProspectFitProjection:
    if not applicable:
        return ProspectFitProjection(False, None, None, None, Decimal(), "NOT_APPLICABLE", CONFIGURATION_VERSION, (), ())

    evidence = (account.provenance.source_record_id,) if account.provenance else ()
    approved_markets = set(PRIMARY_MARKET_ORDER)
    in_primary_cohort = bool(approved_markets.intersection(account.industries))
    factors: list[ProspectFitFactor] = []
    for key, label, weight in _DEFINITIONS:
        if key == "target_cohort_match" and account.industries:
            points = weight if in_primary_cohort else Decimal()
            reason = (
                "The canonical account classification includes an approved primary BTX market."
                if in_primary_cohort
                else "The canonical account classification is outside the approved primary BTX markets."
            )
            factors.append(ProspectFitFactor(key, label, weight, points, reason, evidence))
        else:
            factors.append(ProspectFitFactor(key, label, weight, None, f"{label} requires additional scoped evidence."))

    known = sum((factor.points for factor in factors if factor.points is not None), Decimal())
    missing_weight = sum((factor.weight for factor in factors if factor.points is None), Decimal())
    observed_weight = Decimal(100) - missing_weight
    coverage = (observed_weight / Decimal(100)).quantize(Decimal(".01"))
    complete = missing_weight == 0
    missingness = tuple(f"{factor.label}: missing scoped input" for factor in factors if factor.points is None)
    return ProspectFitProjection(
        True,
        known if complete else None,
        known,
        known + missing_weight,
        coverage,
        "AVAILABLE" if complete else "PARTIAL_RANGE",
        CONFIGURATION_VERSION,
        tuple(factors),
        missingness,
    )


def prospect_fit_payload(projection: ProspectFitProjection) -> dict:
    return {
        "name": "Prospect Fit",
        "applicable": projection.applicable,
        "score": projection.score,
        "score_low": projection.score_low,
        "score_high": projection.score_high,
        "coverage": projection.coverage,
        "status": projection.status,
        "configuration_version": projection.configuration_version,
        "factors": [
            {
                "name": factor.key,
                "label": factor.label,
                "weight": factor.weight,
                "points": factor.points,
                "reason": factor.reason,
                "evidence_ids": factor.evidence_ids,
            }
            for factor in projection.factors
        ],
        "missingness": projection.missingness,
        "interpretation": "Missing factors are not reweighted. The displayed range is the known total through the maximum possible total.",
    }
