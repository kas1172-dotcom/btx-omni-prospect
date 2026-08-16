from btx_omni.providers.sample.environment import (
    INDUSTRIES,
    ROLE_FAMILIES,
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
    assert all(account.id and account.legal_name and account.domain and account.relationship and account.contact_role_families and account.provenance for account in environment.accounts)
    assert all(account.contact_role_families == ROLE_FAMILIES for account in environment.accounts)
    assert sum(account.public_research_state == "RESEARCHED_PUBLIC" for account in environment.accounts) == 78
    assert all(facility.city and facility.region and facility.country == "US" and facility.latitude and facility.longitude for facility in environment.facilities)
    assert {(rank.account_id, rank.industry, rank.rank) for rank in environment.ranks}
    assert all("never an attractiveness input" in rank.methodology.lower() for rank in environment.ranks)


def test_deep_scenario_accounts_have_safe_context() -> None:
    environment = build_sample_environment()
    assert len(environment.commercial_contexts) == 18
    assert len(environment.paperless_accounts) == 17
    assert len(environment.quotes) == 18
    assert all("drawing" not in field.lower() for quote in environment.quotes for field in quote.__dict__)
    statuses = {quote.status.value for quote in environment.quotes}
    assert {"OPEN", "WON", "LOST"} <= statuses
    assert not [quote for quote in environment.quotes if quote.account_id == "acct-06-002"]
    assert len([quote for quote in environment.quotes if quote.account_id == "acct-02-001"]) == 2
    assert {quote.business_unit for quote in environment.quotes if quote.account_id == "acct-01-005"} == {"Southwest", "Defense"}
    assert any(quote.quote_to_book_evidence_ids == ("award-defense-1",) for quote in environment.quotes)


def test_deep_accounts_have_all_source_shaped_poc_contexts() -> None:
    environment = build_sample_environment()
    deep_ids = {context.account_id for context in environment.commercial_contexts}
    assert len(deep_ids) == 17
    assert deep_ids == {item.canonical_account_id for item in environment.paperless_accounts}
    assert {quote.account_id for quote in environment.quotes} < deep_ids
    assert deep_ids == {item.account_id for item in environment.crm_contexts}
    assert deep_ids == {item.account_id for item in environment.public_signals}
    assert deep_ids == set(environment.scoring_inputs)
    assert all(item.contact_role_families and item.deal_ids and item.activity_ids and item.provenance for item in environment.crm_contexts)
    assert all(context.business_unit and context.currency and context.customer_segment and context.end_market and context.monthly_history and context.provenance for context in environment.commercial_contexts)
    assert all("POC synthetic assumption / pending PRISM confirmation" in item for context in environment.commercial_contexts for item in context.jamie_validation_required)


def test_southwest_and_medical_persona_scenarios_are_representable() -> None:
    environment = build_sample_environment()
    accounts = {account.id: account for account in environment.accounts}
    southwest = [accounts[account_id] for account_id in environment.scenario_accounts["southwest-trip"]]
    medical = [accounts[account_id] for account_id in environment.scenario_accounts["medical-whitespace"]]
    assert southwest[0].relationship.value == "CURRENT_CUSTOMER"
    assert {account.industries[0] for account in southwest[1:]} >= {"Semiconductor", "Space"}
    assert {account.industries[0] for account in medical} == {"Medical Device"}
    assert {account.relationship.value for account in medical} == {"CURRENT_CUSTOMER", "TARGET"}
