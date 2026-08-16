from datetime import UTC, datetime
from decimal import Decimal

from btx_omni.domain.scores import ExternalIndustryRank, ScoreStatus
from btx_omni.modules.scoring.account_attractiveness import (
    CONFIGURATION_VERSION,
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_canonical_score_calculation_is_deterministic_and_versioned() -> None:
    result = calculate_account_attractiveness(AccountAttractivenessInputs({"program_durability.expected_production_horizon": "TEN_PLUS_YEARS", "strategic_target_fit": "CORE_TARGET_ARCHETYPE"}), evidence_ids=("ev-a",), calculated_at=NOW)
    assert result.score == Decimal("100.00")
    assert result.configuration_version == CONFIGURATION_VERSION
    assert result.evidence_ids == ("ev-a",)


def test_missingness_is_not_scored_as_zero() -> None:
    result = calculate_account_attractiveness(AccountAttractivenessInputs(), evidence_ids=(), calculated_at=NOW)
    assert result.status is ScoreStatus.INSUFFICIENT_DATA
    assert result.score is None


def test_external_rank_is_separate_from_attractiveness_inputs() -> None:
    rank = ExternalIndustryRank("acct-1", "Defense", 1, "sample", "external")
    score = calculate_account_attractiveness(AccountAttractivenessInputs(), evidence_ids=(), calculated_at=NOW)
    assert rank.rank == 1
    assert score.score is None
