from btx_omni.modules.scoring.prospect_fit import prospect_fit_projection
from btx_omni.providers.sample.environment import build_sample_environment


def test_textron_prospect_fit_is_a_bounded_partial_range_without_reweighting():
    environment = build_sample_environment()
    textron = next(account for account in environment.accounts if account.id == "textron")

    result = prospect_fit_projection(textron, applicable=True)

    assert result.score is None
    assert result.score_low == 30
    assert result.score_high == 100
    assert result.coverage == Decimal("0.30")
    assert result.configuration_version == "prospect-fit-v2.0"
    assert result.factors[0].evidence_ids


def test_prospect_fit_is_not_applied_to_customer_without_prospect_scope():
    environment = build_sample_environment()
    boeing = next(account for account in environment.accounts if account.id == "boeing")

    result = prospect_fit_projection(boeing, applicable=False)

    assert result.status == "NOT_APPLICABLE"
    assert result.score_low is None
from decimal import Decimal
