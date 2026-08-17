from pathlib import Path

from btx_omni.monitor.resolution import resolve_entity
from btx_omni.providers.research.ingestion import load_research_accounts
from btx_omni.providers.sample.environment import build_sample_environment


def test_researched_identities_are_mapped_without_replacing_sample_commercial_scenarios() -> None:
    environment = build_sample_environment()

    assert len(environment.researched_accounts) == len(environment.research_mappings) == 78
    assert all(account.id not in environment.scenario_accounts["defense-award-quote"] for account in environment.accounts if account.research_account_id)
    assert all(account.provenance and account.provenance.synthetic for account in environment.accounts)
    assert all(account.prospect_research_priority is None or account.id not in environment.scoring_inputs for account in environment.accounts)


def test_public_relationship_and_contacts_remain_research_truth_not_crm() -> None:
    environment = build_sample_environment()
    researched = [account for account in environment.accounts if account.research_account_id]
    public_relationships = [account for account in researched if account.public_relationship and account.public_relationship.state.value == "PUBLICLY_EVIDENCED_RELATIONSHIP"]
    named = [contact for account in researched for contact in account.public_contacts if contact.contact_type == "NAMED_PUBLIC_CONTACT"]

    assert len(public_relationships) == 3
    assert all(account.public_relationship and account.public_relationship.state.value != "BTX_CONFIRMED" and account.public_relationship.replaceable_by_internal for account in researched)
    assert any(contact.verification_state == "VERIFIED_OFFICIAL" for contact in named)
    assert any(contact.verification_state == "PUBLIC_PROFILE_VERIFIED" and contact.provenance.research_only for contact in named)
    assert all(contact.provenance.research_only for contact in named)


def test_role_targets_missing_identifiers_and_watch_profile_resolution_are_preserved() -> None:
    environment = build_sample_environment()
    records = load_research_accounts()
    boeing = next(account for account in records if account.research_account_id == "boeing")

    assert boeing.watch_profile.get("sec_cik") is None and boeing.watch_profile.get("ticker") is None
    assert all(account.contact_role_families for account in environment.accounts)
    resolved = resolve_entity("Boeing", environment.watch_profiles)
    assert resolved.canonical_account_id == environment.research_mappings["boeing"]
    assert resolve_entity("unrelated entity", environment.watch_profiles).state.value == "UNRESOLVED"


def test_research_ingestion_has_no_named_company_application_special_case() -> None:
    implementation = Path(__file__).parents[1] / "src" / "btx_omni" / "providers" / "research" / "ingestion.py"
    source = implementation.read_text(encoding="utf-8").casefold()

    assert "lockheed" not in source and "boeing" not in source and "honeywell" not in source
