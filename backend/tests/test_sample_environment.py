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


def test_deep_scenario_accounts_have_safe_context() -> None:
    environment = build_sample_environment()
    assert len(environment.commercial_contexts) == 17
    assert len(environment.quotes) == 17
    assert all("drawing" not in field.lower() for quote in environment.quotes for field in quote.__dict__)
