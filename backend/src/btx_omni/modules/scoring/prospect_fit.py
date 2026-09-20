"""Deterministic Prospect Fit v2 projection from explicit canonical evidence.

Missing factors are not reweighted. The seller sees the bounded low/high result
required by the approved rubric until every applicable factor is known.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from btx_omni.core.clock import as_of_date

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


def _points(key, raw):
    bins = {
        'target_cohort_match': {'PRIMARY': 100, 'ADJACENT': 75, 'EXPLORATORY': 50, 'EXCLUDED': 0},
        'manufacturing_fit': {'TWO_MATCHING_SITES': 100, 'ONE_MATCHING_SITE': 75, 'PARENT_OVERLAP': 50, 'COMPONENT_ADJACENCY': 25, 'MISMATCH': 0},
        'outsourcing_posture': {'ACTIVE_RELEVANT_SOURCING': 100, 'EXTERNAL_SUPPLIERS': 75, 'MIXED': 50, 'HISTORICAL': 25, 'CURRENT_CAPTIVE': 0},
        'strategic_archetype': {'OEM_PRIME_BUYING_AUTHORITY': 100, 'TIER_ONE': 75, 'COMPONENT_MANUFACTURER': 50, 'INTERMEDIARY': 25, 'NO_BUYING_FUNCTION': 0},
        'existing_btx_access': {'BUYER_TWO_WAY': 100, 'WILLING_INTRODUCER': 75, 'QUOTE_WITHIN_365_DAYS': 50, 'RELEVANT_NAMED_CONTACT': 25, 'RESEARCHED_NO_ACCESS': 0},
    }
    if key != 'scale':
        return bins[key].get(raw.get('state'))
    try:
        revenue = Decimal(str(raw.get('organization_ttm_revenue_usd')))
    except InvalidOperation:
        return None
    if not revenue.is_finite() or revenue < 0:
        return None
    return 100 if revenue >= 1_000_000_000 else 75 if revenue >= 100_000_000 else 50 if revenue >= 25_000_000 else 25 if revenue > 0 else 0


def prospect_fit_projection(account, *, applicable: bool, as_of: date | None = None) -> ProspectFitProjection:
    if not applicable:
        return ProspectFitProjection(False, None, None, None, Decimal(), "NOT_APPLICABLE", CONFIGURATION_VERSION, (), ())

    evidence = (account.provenance.source_record_id,) if account.provenance else ()
    approved_markets = set(PRIMARY_MARKET_ORDER)
    in_primary_cohort = bool(approved_markets.intersection(account.industries))
    factors: list[ProspectFitFactor] = []
    for key, label, weight in _DEFINITIONS:
        raw = account.prospect_fit_evidence.get(key, {})
        clock = as_of_date(as_of)
        try:
            age = (clock - date.fromisoformat(raw.get('reviewed_as_of', ''))).days if clock else None
        except (ValueError, TypeError):
            age = None
        valid = (raw.get('account_id') == account.id and raw.get('evidence_ids') and raw.get('source_urls')
                 and raw.get('review_state') == 'VERIFIED' and age is not None and 0 <= age <= (30 if key == 'existing_btx_access' else 180))
        normalized = _points(key, raw) if valid else None
        if normalized is not None:
            factors.append(ProspectFitFactor(key, label, weight, Decimal(normalized) * weight / 100,
                raw.get('reason') or f'{label} follows the documented organization evidence.', tuple(raw['evidence_ids'])))
        elif key == "target_cohort_match" and account.industries and evidence and not raw:
            points = weight if in_primary_cohort else None
            reason = (
                "The canonical account classification includes an approved primary BTX market."
                if in_primary_cohort
                else "An adjacent, exploratory or excluded classification has not been reviewed."
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
