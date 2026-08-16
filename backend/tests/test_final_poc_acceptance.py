from datetime import UTC, datetime

from btx_omni.domain.common import EvidenceState, MatchState
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.providers.sample.environment import (
    INDUSTRIES,
    SCENARIOS,
    build_sample_environment,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_final_manifest_and_scenario_matrix_acceptance() -> None:
    sample = build_sample_environment()
    accounts = {item.id: item for item in sample.accounts}
    assert len(sample.accounts) == 600
    assert {industry: sum(industry in account.industries for account in sample.accounts) for industry in INDUSTRIES} == {industry: 100 for industry in INDUSTRIES}
    assert len({context.account_id for context in sample.commercial_contexts}) == 17
    assert len(sample.scenario_accounts) == len(SCENARIOS)
    assert all(item.provenance and item.contact_role_families for item in sample.accounts)
    assert all(item.latitude is not None and item.longitude is not None for item in sample.facilities)
    assert all(item.account_id in accounts for item in sample.quotes)
    assert all(item.owner_id and item.deal_ids and item.activity_ids for item in sample.crm_contexts)
    assert sample.scenario_accounts["southwest-trip"][0] == "acct-01-001"
    assert {accounts[item].industries[0] for item in sample.scenario_accounts["medical-whitespace"]} == {"Medical Device"}
    assert sample.scenario_accounts["defense-award-quote"] == ("acct-02-001",)
    assert sample.scenario_accounts["semiconductor-expansion"] == ("acct-04-002",)


def test_final_decisioning_truth_and_workflow_acceptance() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW)
    assert {item.type.value for item in alerts} >= {"CUSTOMER_INACTIVITY", "STALE_QUOTE", "CROSS_BU_COORDINATION", "BOOKINGS_DECLINE", "CRM_INACTIVITY"}
    assert match_component_to_quote(sample.matching_components[0], sample.matching_quotes[0]).method is MatchState.EXACT_PART
    assert match_component_to_quote(sample.matching_components[1], sample.matching_quotes[0]).method is MatchState.STRUCTURED_SIMILARITY
    events = {item.account_name: item for item in sample.intelligence_events}
    assert events["External Top Target"].evidence_state is EvidenceState.INFERRED
    assert events["Internal Core Customer"].evidence_state is EvidenceState.CONFIRMED
    assert events["Conflicted Evidence Labs"].evidence_state is EvidenceState.CONFLICTING
    omni = OmniOrchestrator().answer(sample, account_id="acct-01-003", question="Why is this dormant?", observed_at=NOW)
    assert "CUSTOMER_INACTIVITY" in omni.content and not omni.source_of_record
