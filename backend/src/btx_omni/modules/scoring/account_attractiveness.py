"""Legacy account projection of the fixed-weight opportunity rubric.

The compatibility name does not establish an opportunity's qualification.
Missing leaves retain their weights and produce bounds, never a higher score.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from btx_omni.domain.scores import ScoreStatus

CONFIGURATION_VERSION = "account-attractiveness-v2-fixed-weights"
SCORE_UNIT = "STRUCTURAL_INDEX_0_TO_100"
SELLER_PRESENTATION_MINIMUM_COVERAGE = Decimal(".50")
INTERPRETATION_NOTE = "Fixed-weight rubric index, not a probability. Missing inputs produce a range; account context does not qualify a specific pursuit."


@dataclass(frozen=True)
class RubricBin:
    key: str
    label: str
    points: int

    def __post_init__(self) -> None:
        if not 0 <= self.points <= 100:
            raise ValueError("rubric points must be between zero and 100")


@dataclass(frozen=True)
class Rubric:
    key: str
    label: str
    bins: tuple[RubricBin, ...]

    def bin_for(self, key: str) -> RubricBin:
        for bin_ in self.bins:
            if bin_.key == key:
                return bin_
        raise ValueError(f"{key!r} is not a bin of {self.key!r}")


def _rubric(key: str, label: str, *bins: tuple[str, str, int]) -> Rubric:
    return Rubric(key, label, tuple(RubricBin(*bin_) for bin_ in bins))


HORIZON = _rubric("expected_production_horizon", "Expected production horizon", ("TEN_PLUS_YEARS", "10+ years", 100), ("FIVE_TO_NINE_YEARS", "5-9 years", 80), ("TWO_TO_FOUR_YEARS", "2-4 years", 55), ("UNDER_TWO_YEARS_OR_ONE_OFF", "<2 years or one-off", 25))
REPEAT = _rubric("repeat_production_pattern", "Repeat production pattern", ("ESTABLISHED_RECURRING", "established recurring", 100), ("MULTIPLE_BATCHES_NOT_LOCKED", "multiple batches", 70), ("SINGLE_DEFINED_RUN", "single run", 30))
COMMITMENT = _rubric("commitment_strength", "Commitment strength", ("FUNDED_AWARDED_CONTRACTED", "funded/awarded", 100), ("BUDGETED_CREDIBLE_FUNDING", "credible funding", 70), ("EARLY_STAGE_CONDITIONAL", "early/conditional", 40), ("CANCELLATION_OR_FUNDING_RISK", "risk", 20))
MATURITY = _rubric("industry_specific_maturity_evidence", "Industry maturity evidence", ("STRONG_EVIDENCE", "strong", 100), ("PARTIAL_CREDIBLE", "partial", 60), ("WEAK_EARLY", "weak", 30))
MATERIAL = _rubric("material_match", "Material match", ("ROUTINE", "routine", 100), ("EXTENDED_ANALOGOUS", "analogous", 70), ("KNOWN_MISMATCH", "mismatch", 20))
PROCESS = _rubric("process_tolerance_match", "Process / tolerance match", ("ROUTINE", "routine", 100), ("EDGE_BUT_ANALOGOUS", "analogous", 70), ("KNOWN_MISMATCH", "mismatch", 20))
CERT = _rubric("certification_compliance_fit", "Certification fit", ("ALL_MET", "all met", 100), ("MINOR_GAP", "minor gap", 70), ("MAJOR_GAP", "major gap", 20))
VOLUME = _rubric("volume_compatibility", "Volume compatibility", ("NORMAL_RANGE", "normal", 100), ("WORKABLE_NOT_IDEAL", "workable", 70), ("POOR_FIT", "poor", 30))
CONTENT = _rubric("btx_relevant_component_content", "BTX-relevant component content", ("MULTIPLE_FAMILIES", "multiple", 100), ("ONE_FAMILY", "one", 75), ("LIMITED_SET", "limited", 50), ("MINIMAL", "minimal", 20))
REPEAT_VOLUME = _rubric("repeat_volume_potential", "Repeat volume potential", ("LARGE_RECURRING", "large", 100), ("MEANINGFUL_RECURRING", "meaningful", 75), ("SMALL_EPISODIC", "small", 40), ("ONE_OFF", "one-off", 20))
CROSS_BU = _rubric("cross_bu_applicability", "Cross-BU applicability", ("TWO_PLUS_BU", "two+", 100), ("ONE_BU", "one", 70), ("WEAK_OR_NONE", "weak", 20))
MAKE_BUY = _rubric("make_buy_propensity", "Make/buy propensity", ("SOURCES_EXTERNALLY", "external", 100), ("MIXED", "mixed", 60), ("MOSTLY_CAPTIVE", "captive", 30))
AWARDS = _rubric("recent_awards_funding_production_increases", "Recent awards", ("CLEAR_POSITIVE_RECENT", "positive", 100), ("SOME_POSITIVE", "some", 70), ("NO_MATERIAL_CHANGE", "none", 50), ("REDUCTION_OR_CANCELLATION", "reduction", 20))
HIRING = _rubric("program_linked_hiring_staffing", "Program hiring", ("VISIBLE_SURGE", "surge", 100), ("STEADY", "steady", 60), ("NONE", "none", 50), ("VISIBLE_LAYOFFS", "layoffs", 20))
MILESTONES = _rubric("production_delivery_milestones", "Production milestones", ("SCALE_UP_OR_MAJOR", "scale", 100), ("ON_TRACK", "on track", 70), ("NONE_IDENTIFIED", "none", 50), ("DELAY_SLIPPAGE", "delay", 20))
REGULATORY = _rubric("regulatory_funding_events", "Regulatory events", ("MATERIALLY_IMPROVES", "improves", 100), ("STABLE", "stable", 60), ("MATERIALLY_HURTS", "hurts", 20))
STRATEGIC = _rubric("strategic_target_fit", "Strategic Target Fit", ("CORE_TARGET_ARCHETYPE", "core", 100), ("STRONG_TARGET_ARCHETYPE", "strong", 80), ("PLAUSIBLE_UNCLEAR", "plausible", 60), ("INDUSTRY_ADJACENT_WEAK", "weak", 40), ("UNLIKELY", "unlikely", 20))
ADJACENCY = _rubric("btx_commercial_adjacency", "BTX Commercial Adjacency", ("EXISTING_MULTI_BU_ACTIVE", "multi BU", 100), ("EXISTING_ONE_BU_ACTIVE", "one BU", 85), ("PRIOR_CUSTOMER_WARM_CRM", "warm CRM", 75), ("QUOTE_OR_WARM_NO_SALES", "quote/warm", 65), ("ANALOGOUS_HISTORY_NO_DIRECT", "analogous", 60), ("COLD_PROSPECT", "cold", 50))


@dataclass(frozen=True)
class SubfactorWeight:
    rubric: Rubric
    weight: Decimal


@dataclass(frozen=True)
class FactorDefinition:
    key: str
    label: str
    weight: Decimal
    subfactors: tuple[SubfactorWeight, ...] = ()
    single_rubric: Rubric | None = None


def _factor(key: str, label: str, weight: str, *items: tuple[Rubric, str]) -> FactorDefinition:
    return FactorDefinition(key, label, Decimal(weight), tuple(SubfactorWeight(r, Decimal(w)) for r, w in items))


FACTORS = (
    _factor("program_durability", "Program Durability", ".30", (HORIZON, ".40"), (REPEAT, ".30"), (COMMITMENT, ".20"), (MATURITY, ".10")),
    _factor("btx_manufacturing_fit", "BTX Manufacturing Fit", ".25", (MATERIAL, ".30"), (PROCESS, ".30"), (CERT, ".20"), (VOLUME, ".20")),
    _factor("addressable_btx_work", "Addressable BTX Work", ".15", (CONTENT, ".40"), (REPEAT_VOLUME, ".30"), (CROSS_BU, ".20"), (MAKE_BUY, ".10")),
    _factor("program_momentum", "Program Momentum", ".10", (AWARDS, ".40"), (HIRING, ".20"), (MILESTONES, ".20"), (REGULATORY, ".20")),
    FactorDefinition("strategic_target_fit", "Strategic Target Fit", Decimal(".10"), single_rubric=STRATEGIC),
    FactorDefinition("btx_commercial_adjacency", "BTX Commercial Adjacency", Decimal(".10"), single_rubric=ADJACENCY),
)


@dataclass(frozen=True)
class AccountAttractivenessInputs:
    selections: Mapping[str, str] = field(default_factory=dict)
    evidence_by_factor: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class FactorResult:
    key: str
    configured_weight: Decimal
    effective_weight: Decimal | None
    factor_score: Decimal | None
    missing: bool
    missing_subfactors: tuple[str, ...]
    contribution: Decimal | None = None
    input_coverage: Decimal = Decimal()
    evidence_ids: tuple[str, ...] = ()
    score_low: Decimal = Decimal(0)
    score_high: Decimal = Decimal(100)


@dataclass(frozen=True)
class AccountAttractivenessResult:
    configuration_version: str
    status: ScoreStatus
    score: Decimal | None
    coverage: Decimal
    factors: tuple[FactorResult, ...]
    missingness: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    calculated_at: datetime
    hypothesis: bool = True
    interpretation_note: str = INTERPRETATION_NOTE
    score_range: Mapping[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class SellerAttractivenessProjection:
    """The sole seller-facing contract; never exposes an ineligible raw score."""

    score: Decimal | None
    coverage: Decimal
    status: str
    score_unit: str
    configuration_version: str
    hypothesis: bool
    data_mode: str
    interpretation_note: str
    factors: tuple[FactorResult, ...]
    missingness: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    exclusion_reason: str | None = None
    score_range: Mapping[str, Decimal] = field(default_factory=dict)


def subfactor_path(factor_key: str, subfactor_key: str) -> str:
    return f"{factor_key}.{subfactor_key}"


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def calculate_account_attractiveness(inputs: AccountAttractivenessInputs, *, evidence_ids: tuple[str, ...], calculated_at: datetime) -> AccountAttractivenessResult:
    valid_keys = {f.key for f in FACTORS if f.single_rubric} | {subfactor_path(f.key, s.rubric.key) for f in FACTORS for s in f.subfactors}
    if set(inputs.selections) - valid_keys:
        raise ValueError('Unknown factor cannot modify the approved opportunity rubric')
    raw: list[tuple[FactorDefinition, Decimal | None, tuple[str, ...], Decimal]] = []
    for factor in FACTORS:
        if factor.single_rubric:
            key = factor.key
            selected = inputs.selections.get(key)
            raw.append((factor, Decimal(factor.single_rubric.bin_for(selected).points) if selected else None, () if selected else (factor.single_rubric.label,), Decimal(1) if selected else Decimal()))
            continue
        available = [(item, inputs.selections.get(subfactor_path(factor.key, item.rubric.key))) for item in factor.subfactors]
        known = [(item, selected) for item, selected in available if selected]
        missing = tuple(item.rubric.label for item, selected in available if not selected)
        if not known:
            raw.append((factor, None, missing, Decimal()))
        else:
            total = sum((item.weight for item, _ in known), Decimal())
            score = sum((Decimal(item.rubric.bin_for(selected).points) * item.weight for item, selected in known), Decimal())
            raw.append((factor, score, missing, total))
    coverage = sum((factor.weight for factor, _, _, factor_coverage in raw if factor_coverage == 1), Decimal())
    missingness = tuple(message for factor, score, names, _ in raw for message in (
        (f"{factor.label}: missing",) if score is None else tuple(f"{factor.label} > {name}: missing" for name in names)
    ))
    results = []
    low, high = Decimal(), Decimal()
    for factor, score, missing, factor_coverage in raw:
        floor = score if score is not None else Decimal()
        ceiling = floor + 100 * (1 - factor_coverage)
        low += floor * factor.weight
        high += ceiling * factor.weight
        complete = factor_coverage == 1
        results.append(FactorResult(factor.key, factor.weight, factor.weight,
                                    score if complete else None, not complete, missing,
                                    _round2(floor * factor.weight) if complete else None,
                                    factor_coverage, score_low=floor, score_high=ceiling))
    return AccountAttractivenessResult(CONFIGURATION_VERSION,
        ScoreStatus.AVAILABLE if coverage == 1 else ScoreStatus.INSUFFICIENT_DATA,
        _round2(low) if coverage == 1 else None, coverage, tuple(results), missingness,
        evidence_ids, calculated_at, score_range={"low": _round2(low), "high": _round2(high)})


def seller_attractiveness_projection(inputs: AccountAttractivenessInputs, *, calculated_at: datetime, excluded: bool = False, exclusion_reason: str | None = None) -> SellerAttractivenessProjection:
    """Apply the shared seller presentation policy to simulated rubric inputs.

    Scenario selections are hypothesis inputs, not observed evidence.  Until a
    factor has genuine evidence attached, this projection deliberately exposes
    no factor-level evidence references.
    """
    evidence_ids = tuple(sorted({eid for values in inputs.evidence_by_factor.values() for eid in values}))
    result = calculate_account_attractiveness(inputs, evidence_ids=evidence_ids, calculated_at=calculated_at)
    factors = tuple(replace(factor, evidence_ids=tuple(sorted({eid for key, values in inputs.evidence_by_factor.items() if key == factor.key or key.startswith(factor.key + ".") for eid in values}))) for factor in result.factors)
    eligible = not excluded and result.score is not None and result.coverage >= SELLER_PRESENTATION_MINIMUM_COVERAGE
    status = "UNAVAILABLE" if excluded or result.coverage == 0 else ("SIMULATED_BTX_CONTEXT" if eligible else "NEEDS_RESEARCH")
    return SellerAttractivenessProjection(result.score if eligible else None, result.coverage, status, SCORE_UNIT, result.configuration_version, True, "SIMULATED_HYPOTHESIS", result.interpretation_note, factors, result.missingness, evidence_ids, exclusion_reason, {} if excluded else result.score_range)
