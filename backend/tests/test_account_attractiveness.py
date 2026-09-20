from datetime import UTC, datetime
from decimal import Decimal

from btx_omni.domain.scores import ExternalIndustryRank, ScoreStatus
from btx_omni.modules.scoring.account_attractiveness import (
    CONFIGURATION_VERSION,
    FACTORS,
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
    seller_attractiveness_projection,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_canonical_score_calculation_is_deterministic_and_versioned() -> None:
    result = calculate_account_attractiveness(AccountAttractivenessInputs({"program_durability.expected_production_horizon": "TEN_PLUS_YEARS", "strategic_target_fit": "CORE_TARGET_ARCHETYPE"}), evidence_ids=("ev-a",), calculated_at=NOW)
    assert result.score is None
    assert result.score_range == {"low": Decimal(22), "high": Decimal(100)}
    assert result.configuration_version == CONFIGURATION_VERSION
    assert result.evidence_ids == ("ev-a",)


def test_missingness_is_not_scored_as_zero() -> None:
    result = calculate_account_attractiveness(AccountAttractivenessInputs(), evidence_ids=(), calculated_at=NOW)
    assert result.status is ScoreStatus.INSUFFICIENT_DATA
    assert result.score is None
    assert result.coverage == Decimal(0)
    assert len(result.missingness) == len(FACTORS)


def test_coverage_counts_only_usable_complete_factors_but_bounds_retain_known_leaves() -> None:
    result = calculate_account_attractiveness(AccountAttractivenessInputs({"program_durability.expected_production_horizon": "TEN_PLUS_YEARS", "strategic_target_fit": "CORE_TARGET_ARCHETYPE"}), evidence_ids=(), calculated_at=NOW)
    assert result.coverage == Decimal(".10")
    assert result.score_range['low'] == 22
    assert result.factors[0].input_coverage == Decimal(".40")
    assert result.factors[0].factor_score is None
    assert result.factors[0].score_low == 40
    assert result.factors[0].score_high == 100


def test_complete_score_is_fixed_weight_sum_and_missing_leaf_cannot_raise_it():
    selections = {f.key if f.single_rubric else f"{f.key}.{s.rubric.key}": (f.single_rubric or s.rubric).bins[0].key for f in FACTORS for s in (f.subfactors or (None,))}
    selections["program_durability.expected_production_horizon"] = "UNDER_TWO_YEARS_OR_ONE_OFF"
    complete = calculate_account_attractiveness(AccountAttractivenessInputs(selections), evidence_ids=(), calculated_at=NOW)
    assert complete.score == 91
    assert complete.score_range == {"low": 91, "high": 91}
    del selections["program_durability.expected_production_horizon"]
    partial = calculate_account_attractiveness(AccountAttractivenessInputs(selections), evidence_ids=(), calculated_at=NOW)
    assert partial.score is None
    assert partial.score_range == {"low": 88, "high": 100}
    assert sum(f.effective_weight for f in partial.factors) == 1


def test_fully_populated_rubric_has_complete_coverage() -> None:
    selections = {f.key if f.single_rubric else f"{f.key}.{s.rubric.key}": (f.single_rubric or s.rubric).bins[0].key for f in FACTORS for s in (f.subfactors or (None,))}
    assert calculate_account_attractiveness(AccountAttractivenessInputs(selections), evidence_ids=(), calculated_at=NOW).coverage == Decimal("1.00")


def test_seller_projection_hides_low_coverage_raw_score_and_has_no_identity_evidence() -> None:
    projection = seller_attractiveness_projection(AccountAttractivenessInputs({"program_durability.expected_production_horizon": "TEN_PLUS_YEARS", "strategic_target_fit": "CORE_TARGET_ARCHETYPE"}), calculated_at=NOW)
    assert projection.score is None
    assert projection.status == "NEEDS_RESEARCH"
    assert projection.evidence_ids == ()
    assert all(not factor.evidence_ids for factor in projection.factors)


def test_external_rank_is_separate_from_attractiveness_inputs() -> None:
    rank = ExternalIndustryRank("acct-1", "Defense", 1, "sample", "external")
    score = calculate_account_attractiveness(AccountAttractivenessInputs(), evidence_ids=(), calculated_at=NOW)
    assert rank.rank == 1
    assert score.score is None


def test_evidence_is_attached_only_to_the_supported_factor():
    inputs = AccountAttractivenessInputs({"btx_commercial_adjacency": "EXISTING_ONE_BU_ACTIVE"}, {"btx_commercial_adjacency": ("accepted-revenue-1",)})
    projection = seller_attractiveness_projection(inputs, calculated_at=NOW)
    assert projection.score is None
    assert projection.evidence_ids == ("accepted-revenue-1",)
    assert next(f for f in projection.factors if f.key == "btx_commercial_adjacency").evidence_ids == ("accepted-revenue-1",)
    assert all(not f.evidence_ids for f in projection.factors if f.key != "btx_commercial_adjacency")
