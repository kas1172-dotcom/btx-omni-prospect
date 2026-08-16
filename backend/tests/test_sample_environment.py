from btx_omni.providers.sample.environment import (
    INDUSTRIES,
    SCENARIOS,
    build_sample_environment,
)


def test_market_universe_is_complete_and_mappable() -> None:
    environment = build_sample_environment()
    assert len(environment.accounts) == 600
    assert {rank.industry for rank in environment.ranks} == set(INDUSTRIES)
    assert len(environment.facilities) == len(environment.accounts)
    assert len(environment.scenario_accounts) == len(SCENARIOS)
    assert all(item.latitude is not None and item.longitude is not None for item in environment.facilities)
    assert {industry: sum(industry in account.industries for account in environment.accounts) for industry in INDUSTRIES} == {industry: 100 for industry in INDUSTRIES}
    assert all(account.id and account.relationship and account.contact_role_families and account.provenance for account in environment.accounts)


def test_deep_scenario_accounts_have_safe_context() -> None:
    environment = build_sample_environment()
    assert len(environment.commercial_contexts) == 18
    assert len(environment.quotes) == 17
    assert all("drawing" not in field.lower() for quote in environment.quotes for field in quote.__dict__)


def test_deep_accounts_have_all_source_shaped_poc_contexts() -> None:
    environment = build_sample_environment()
    deep_ids = {context.account_id for context in environment.commercial_contexts}
    assert len(deep_ids) == 17
    assert deep_ids == {quote.account_id for quote in environment.quotes}
    assert deep_ids == {item.account_id for item in environment.crm_contexts}
    assert deep_ids == {item.account_id for item in environment.public_signals}
    assert deep_ids == set(environment.scoring_inputs)
    assert all(item.contact_role_families and item.deal_ids and item.activity_ids and item.provenance for item in environment.crm_contexts)


def test_southwest_and_medical_persona_scenarios_are_representable() -> None:
    environment = build_sample_environment()
    accounts = {account.id: account for account in environment.accounts}
    southwest = [accounts[account_id] for account_id in environment.scenario_accounts["southwest-trip"]]
    medical = [accounts[account_id] for account_id in environment.scenario_accounts["medical-whitespace"]]
    assert southwest[0].relationship.value == "CURRENT_CUSTOMER"
    assert {account.industries[0] for account in southwest[1:]} >= {"Semiconductor", "Space"}
    assert {account.industries[0] for account in medical} == {"Medical Device"}
    assert {account.relationship.value for account in medical} == {"CURRENT_CUSTOMER", "TARGET"}
