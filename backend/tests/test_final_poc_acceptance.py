from datetime import UTC, datetime

from btx_omni.domain.common import MatchState
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.providers.sample.environment import SCENARIOS, build_sample_environment

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_final_manifest_contains_real_companies_and_named_poc_scenarios() -> None:
    sample = build_sample_environment()
    assert len(sample.accounts) == 34
    assert len(sample.scenario_accounts) == len(SCENARIOS)
    assert all(item.research_account_id and item.public_identity for item in sample.accounts)
    assert all(item.account_id in {account.id for account in sample.accounts} for item in sample.quotes)
    assert sample.scenario_accounts["defense-award-quote"] == ("lockheed-martin",)
    assert sample.scenario_accounts["semiconductor-expansion"] == ("intel",)


def test_final_decisioning_and_workflow_acceptance() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW)
    assert {item.type.value for item in alerts} >= {"CUSTOMER_INACTIVITY", "STALE_QUOTE", "CROSS_BU_COORDINATION", "BOOKINGS_DECLINE", "CRM_INACTIVITY"}
    assert match_component_to_quote(sample.matching_components[0], sample.matching_quotes[0]).method is MatchState.EXACT_PART
    omni = OmniOrchestrator().answer(sample, account_id="applied-materials", question="Why is this dormant?", observed_at=NOW)
    assert "CUSTOMER_INACTIVITY" in omni.content and not omni.source_of_record
