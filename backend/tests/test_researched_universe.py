from pathlib import Path

from btx_omni.monitor.resolution import resolve_entity
from btx_omni.providers.research.ingestion import (
    load_research_accounts,
    load_usaspending_recipient_identities,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_researched_identities_are_the_canonical_universe_and_support_simulated_scenarios() -> None:
    environment = build_sample_environment()

    assert len(environment.researched_accounts) == len(environment.research_mappings) > 0
    researched = [account for account in environment.accounts if account.research_account_id]
    assert all(account.id in environment.research_mappings for account in researched)
    assert all(account.provenance and not account.provenance.synthetic for account in environment.accounts)
    assert all(account.research_account_id == account.id for account in researched)
    assert len(environment.rich_scenarios) == 12
    assert all(account.id in environment.scoring_inputs for account in environment.accounts if account.id in environment.rich_scenarios and environment.rich_scenarios[account.id].simulated_score_inputs)


def test_public_relationship_and_contacts_do_not_imply_btx_relationships_or_include_linkedin() -> None:
    environment = build_sample_environment()
    researched = [account for account in environment.accounts if account.research_account_id]
    named = [contact for account in researched for contact in account.public_contacts if contact.contact_type == "NAMED_PUBLIC_CONTACT"]

    assert all(account.public_relationship and account.public_relationship.state.value == "NO_RELATIONSHIP_EVIDENCE" and account.public_relationship.replaceable_by_internal for account in researched)
    assert any("btx" in account.prospect_rationale.casefold() for account in researched)
    assert any(contact.verification_state == "VERIFIED_OFFICIAL" for contact in named)
    assert all(contact.provenance.research_only for contact in named)
    assert all(not (contact.source_url and "linkedin.com" in contact.source_url.casefold()) for contact in named)


def test_role_targets_missing_identifiers_and_watch_profile_resolution_are_preserved() -> None:
    environment = build_sample_environment()
    records = load_research_accounts()
    boeing = next(account for account in records if account.research_account_id == "boeing")

    assert (boeing.watch_profile.get("sec_cik"), boeing.watch_profile.get("ticker")) == ("0000012927", "BA")
    assert all(account.contact_role_families for account in environment.accounts if account.research_account_id)
    resolved = resolve_entity("Boeing", environment.watch_profiles)
    assert resolved.canonical_account_id == environment.research_mappings["boeing"]
    assert resolve_entity("unrelated entity", environment.watch_profiles).state.value == "UNRESOLVED"


def test_usaspending_recipient_legal_names_are_sourced_and_separate_from_marketing_aliases() -> None:
    environment = build_sample_environment()
    mappings = load_usaspending_recipient_identities()
    profiles = {profile.canonical_account_id: profile for profile in environment.watch_profiles}

    assert set(mappings) == {
        "anduril-industries", "blue-origin", "boeing", "ge-aerospace",
        "general-atomics", "intel", "l3harris", "lockheed-martin",
        "northrop-grumman", "rocket-lab-usa", "rtx-collins-aerospace",
        "sierra-space", "spacex", "spirit-aerosystems", "symbotic",
        "terrapower", "textron", "tsmc-arizona", "ula-united-launch-alliance",
    }
    assert all(items and all(item.source_url.startswith("https://") for item in items) for items in mappings.values())
    assert all(profiles[account_id].usaspending_recipient_names == tuple(item.recipient_legal_name for item in items) for account_id, items in mappings.items())
    assert all(
        all(kind and value for kind, value in profile.source_native_identifiers)
        for profile in profiles.values()
    )


def test_research_ingestion_has_no_named_company_application_special_case() -> None:
    implementation = Path(__file__).parents[1] / "src" / "btx_omni" / "providers" / "research" / "ingestion.py"
    source = implementation.read_text(encoding="utf-8").casefold()

    assert "lockheed" not in source and "boeing" not in source and "honeywell" not in source
