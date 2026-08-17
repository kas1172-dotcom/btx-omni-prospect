from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_verified_hq_public_locations_are_the_only_map_locations() -> None:
    environment = build_sample_environment()

    assert len(environment.public_facilities) == 29
    assert all(item.verification_state == "VERIFIED_PUBLIC_HQ" and item.provenance and item.source_url for item in environment.public_facilities)
    assert environment.facilities == environment.public_facilities
    assert {item.account_id for item in environment.public_facilities} <= {item.id for item in environment.accounts}


def test_missing_public_location_has_no_fake_pin_and_feeds_refresh_generic_watch_profiles() -> None:
    environment = build_sample_environment()
    public_ids = {item.account_id for item in environment.public_facilities}
    missing = [item for item in environment.accounts if item.research_account_id and item.id not in public_ids]

    assert len(missing) == 49
    assert all(item.domain and not item.domain.endswith(".sample.invalid") for item in missing)
    assert sum(bool(item.newsroom_url) for item in environment.watch_profiles) == 40
    assert sum(bool(item.investor_relations_url) for item in environment.watch_profiles) == 16
    assert sum(bool(item.official_feed_urls) for item in environment.watch_profiles) == 13
    assert sum(bool(item.facilities) for item in environment.watch_profiles) == 29


def test_ge_aerospace_hq_uses_exact_sec_address_and_census_coordinates() -> None:
    environment = build_sample_environment()
    account_id = environment.research_mappings["ge-aerospace"]
    facility = next(item for item in environment.public_facilities if item.account_id == account_id)

    assert facility.city == "EVENDALE" and facility.region == "OH"
    assert facility.source_url == "https://data.sec.gov/submissions/CIK0000040545.json"
    assert facility.verification_state == "VERIFIED_PUBLIC_HQ"
    assert facility.provenance and "SEC_EDGAR_0000040545" in facility.provenance.source_ids


def test_public_location_does_not_change_account_attractiveness() -> None:
    environment = build_sample_environment()
    account_id = "boeing"

    score = calculate_account_attractiveness(AccountAttractivenessInputs(environment.scoring_inputs[account_id]), evidence_ids=(account_id,), calculated_at=environment.accounts[0].provenance.observed_at)

    assert score.score is not None
