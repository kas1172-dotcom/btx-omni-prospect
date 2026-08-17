from btx_omni.providers.research.scenarios import SCENARIOS as RICH_SCENARIOS
from btx_omni.providers.sample.environment import (
    ROLE_FAMILIES,
    SCENARIOS,
    build_sample_environment,
)


def test_environment_contains_only_researched_public_companies() -> None:
    environment = build_sample_environment()
    assert len(environment.accounts) == len(environment.researched_accounts) == 78
    assert set(environment.research_mappings) == {account.id for account in environment.accounts}
    assert all(account.research_account_id == account.id for account in environment.accounts)
    assert all(account.public_identity and account.public_research_state == "RESEARCHED_PUBLIC" for account in environment.accounts)
    assert all("market target" not in account.legal_name.casefold() for account in environment.accounts)
    assert all(account.contact_role_families == ROLE_FAMILIES for account in environment.accounts)
    assert environment.facilities == environment.public_facilities


def test_simulated_btx_context_is_attached_only_to_curated_real_companies() -> None:
    environment = build_sample_environment()
    scenario_ids = {item.research_account_id for item in RICH_SCENARIOS}
    context_ids = {context.account_id for context in environment.commercial_contexts}
    assert context_ids == scenario_ids
    assert {item.canonical_account_id for item in environment.paperless_accounts} == scenario_ids
    assert {item.account_id for item in environment.crm_contexts} == scenario_ids
    assert {quote.account_id for quote in environment.quotes} <= scenario_ids
    assert all("POC simulation" in note for context in environment.commercial_contexts for note in context.jamie_validation_required)
    assert len(environment.rich_scenarios) == 12


def test_seller_scenarios_use_real_companies_and_public_geography() -> None:
    environment = build_sample_environment()
    accounts = {account.id: account for account in environment.accounts}
    assert len(environment.scenario_accounts) == len(SCENARIOS)
    assert set(environment.scenario_accounts["southwest-trip"]) <= set(accounts)
    assert accounts[environment.scenario_accounts["medical-whitespace"][0]].industries[0] == "Medical Device"
    assert environment.scenario_accounts["defense-award-quote"] == ("lockheed-martin",)
    assert all(facility.verification_state.startswith("VERIFIED_PUBLIC") for facility in environment.public_facilities)
