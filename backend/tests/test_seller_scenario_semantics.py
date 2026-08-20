from datetime import UTC, datetime
from decimal import Decimal

from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.domain.common import DataMode
from btx_omni.domain.quotes import QuoteStatus
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.intelligence.signals import SignalKind, SourceValidationState
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.providers.sample.environment import SCENARIOS, build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def _score(sample, account_id: str):
    scenario = sample.rich_scenarios[account_id]
    return calculate_account_attractiveness(
        AccountAttractivenessInputs(scenario.simulated_score_inputs),
        evidence_ids=(),
        calculated_at=NOW,
    )


def test_canonical_seller_scenarios_assert_their_defining_evidence() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW, orders=sample.orders)
    events = sample.rich_scenarios

    assert set(sample.scenario_accounts) == set(SCENARIOS)

    # Southwest trip: only sourced Southern California facility records are in scope.
    assert sample.scenario_accounts["southwest-trip"] == ("anduril-industries", "rocket-lab-usa", "general-atomics")
    trip_facilities = [item for item in sample.public_facilities if item.account_id in sample.scenario_accounts["southwest-trip"]]
    assert {item.account_id for item in trip_facilities} == set(sample.scenario_accounts["southwest-trip"])
    assert all(item.region == "CA" and item.provenance.source_urls for item in trip_facilities)

    # Medical whitespace: low coverage is explicit; it is not a claim that all internal data is absent.
    medtronic = _score(sample, "medtronic")
    assert medtronic.coverage == Decimal("0.20")
    assert events["medtronic"].event.kind is SignalKind.FINANCIAL_REPORT

    # Defense award plus quote history: public and SAMPLE sources stay distinct on Lockheed Martin.
    lockheed_quotes = [item for item in sample.quotes if item.account_id == "lockheed-martin"]
    assert events["lockheed-martin"].event.evidence_state.value == "CONFIRMED"
    assert any(item.status is QuoteStatus.OPEN for item in lockheed_quotes)
    assert all(item.provenance.data_mode is DataMode.SAMPLE and item.provenance.synthetic for item in lockheed_quotes)

    # Semiconductor expansion: Intel's official source is preserved as automation-blocked, not promoted.
    assert events["intel"].event.kind is SignalKind.EXPANSION
    assert events["intel"].event.source_validation_state is SourceValidationState.AUTOMATION_BLOCKED

    # Dormant reactivation: the SAMPLE booking date is beyond the deterministic inactivity window.
    applied_contexts = [item for item in sample.commercial_contexts if item.account_id == "applied-materials"]
    assert all((NOW.date() - item.last_booking_date).days >= CommercialAlertEngine.inactivity_days for item in applied_contexts if item.last_booking_date)
    assert any(item.account_id == "applied-materials" and item.type is CommercialAlertKind.CUSTOMER_INACTIVITY for item in alerts)

    # Quote follow-up: GE Aerospace has an actionable open SAMPLE quote and deterministic follow-up alert.
    ge_quotes = [item for item in sample.quotes if item.account_id == "ge-aerospace"]
    assert any(item.status is QuoteStatus.OPEN and item.provenance.data_mode is DataMode.SAMPLE for item in ge_quotes)
    assert any(item.account_id == "ge-aerospace" and item.type is CommercialAlertKind.QUOTE_FOLLOW_UP for item in alerts)

    # Cross-BU overlap: Boeing remains explicitly unresolved to a single business unit.
    boeing_contexts = [item for item in sample.commercial_contexts if item.account_id == "boeing"]
    assert {item.business_unit for item in boeing_contexts} == {"chandler-industries", "high-tech-solutions"}
    assert any(item.account_id == "boeing" and item.type is CommercialAlertKind.CROSS_BU_COORDINATION for item in alerts)

    # Strong external / weak internal: Intel has the public expansion signal but no SAMPLE commercial context.
    assert sample.scenario_accounts["strong-external-weak-internal"] == ("intel",)
    assert events["intel"].event.kind is SignalKind.EXPANSION
    assert not any(item.account_id == "intel" for item in sample.commercial_contexts)

    # Strong internal / weak external: Lam Research has SAMPLE commercial history but no curated public scenario event.
    lam_contexts = [item for item in sample.commercial_contexts if item.account_id == "lam-research"]
    assert sample.scenario_accounts["strong-internal-weak-external"] == ("lam-research",)
    assert any(item.ttm_revenue_minor and item.ttm_revenue_minor > 100_000_000 for item in lam_contexts)
    assert "lam-research" not in events

    # Uncertainty remains visible: Symbotic is excluded from scoring and Intel's source remains blocked.
    assert sample.scenario_accounts["missing-unresolved-conflicting"] == ("symbotic", "intel")
    assert events["symbotic"].exclusion_reason
    assert events["intel"].event.source_validation_state is SourceValidationState.AUTOMATION_BLOCKED
