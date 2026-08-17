from datetime import UTC, datetime

from btx_omni.modules.intelligence.signals import SourceValidationState
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_rich_scenarios_are_real_public_identities_with_sourced_events() -> None:
    environment = build_sample_environment()
    accounts = {item.id: item for item in environment.accounts}
    assert len(environment.rich_scenarios) == 12
    assert {accounts[account_id].industries[0] for account_id in environment.rich_scenarios} >= {"Commercial Aerospace", "Defense", "Space", "Semiconductor", "Medical", "Robotics"}
    assert all(accounts[account_id].research_account_id and scenario.event.source_url.startswith("https://") for account_id, scenario in environment.rich_scenarios.items())


def test_rich_score_scenarios_have_varied_coverage_and_an_explicit_exclusion() -> None:
    environment = build_sample_environment()
    results = {account_id: calculate_account_attractiveness(AccountAttractivenessInputs(scenario.simulated_score_inputs), evidence_ids=(), calculated_at=datetime(2026, 1, 1, tzinfo=UTC)) for account_id, scenario in environment.rich_scenarios.items() if scenario.simulated_score_inputs}
    scores = [result.score for result in results.values() if result.score is not None]
    assert max(scores) >= 90 and min(scores) <= 60
    assert any(result.coverage < 0.5 for result in results.values())
    assert any(scenario.exclusion_reason for scenario in environment.rich_scenarios.values())


def test_curated_events_record_official_source_validation_without_replacing_blocked_urls() -> None:
    environment = build_sample_environment()
    events = {scenario.research_account_id: scenario.event for scenario in environment.rich_scenarios.values()}

    assert events["anduril-industries"].source_validation_state is SourceValidationState.BROWSER_VERIFIED
    assert events["tsmc-arizona"].source_validation_state is SourceValidationState.BROWSER_VERIFIED
    assert events["applied-materials"].source_validation_state is SourceValidationState.BROWSER_VERIFIED
    assert events["medtronic"].source_validation_state is SourceValidationState.BROWSER_VERIFIED
    assert events["symbotic"].source_validation_state is SourceValidationState.BROWSER_VERIFIED
    assert events["intel"].source_validation_state is SourceValidationState.AUTOMATION_BLOCKED
    assert events["intel"].source_url == "https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-intel"
    assert events["anduril-industries"].occurred_at.date().isoformat() == "2024-10-29"
    assert events["applied-materials"].occurred_at.date().isoformat() == "2025-01-16"
