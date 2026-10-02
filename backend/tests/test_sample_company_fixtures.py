"""Synthetic lineage and scoped foreign keys of named-company SAMPLE records."""

import pytest

from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.named_company_cases import (
    CUSTOMERS,
    EXISTING_PROGRAMS,
    PRE_PURSUIT,
    PURSUITS,
)


@pytest.fixture(scope="module")
def sample():
    return enhance_environment(build_sample_environment())


def _labeled(record):
    assert record["data_mode"] == "SAMPLE"
    assert record["synthetic"] is True
    assert record["source"]


@pytest.mark.parametrize("aid", tuple(CUSTOMERS))
def test_named_customer_records_are_labeled_and_links_reconcile(sample, aid):
    ledger = sample.commercial_ledgers[aid]
    _labeled(ledger)
    for collection in ("programs", "components", "rfqs", "quotes", "quote_revisions",
                       "quote_lines", "orders", "order_lines", "shipments", "acceptances",
                       "revenue_events", "invoices", "payments", "service_events",
                       "role_targets", "interactions", "opportunities", "monthly_commercial_history"):
        for row in ledger[collection]:
            _labeled(row)
    for month in ledger["monthly_commercial_history"]:
        for allocation in month["business_unit_allocations"]:
            _labeled(allocation)
    for key in ("relationship_profile", "bu_revenue_exposure", "ttm_summary"):
        _labeled(ledger[key])
    programs = {row["program_id"] for row in ledger["programs"]}
    components = {row["component_id"]: row for row in ledger["components"]}
    quotes = {row["quote_id"]: row for row in ledger["quotes"]}
    revisions = {row["quote_revision_id"]: row for row in ledger["quote_revisions"]}
    for component in components.values():
        assert component["program_id"] in programs
    for opportunity in ledger["opportunities"]:
        assert opportunity["component_id"] in components
        assert opportunity["program_id"] in programs
        assert opportunity["quote_revision_id"] in revisions
        assert opportunity["delivery_facility_id"] in {f.id for f in sample.btx_facilities}
        _labeled(opportunity["scope_requirements"])
        _labeled(opportunity["qualification_evidence"])
        for observation in opportunity["score_observations"]:
            _labeled(observation)
        for family in opportunity["scoring_inputs"].values():
            for row in family.values():
                _labeled(row)
    for order in ledger["orders"]:
        assert order["quote_id"] in quotes
        assert order["accepted_quote_revision_id"] in revisions
        assert revisions[order["accepted_quote_revision_id"]]["quote_id"] == order["quote_id"]


@pytest.mark.parametrize("aid", tuple(PURSUITS))
def test_named_prospect_pursuit_is_labeled_and_scoped_without_ledger(sample, aid):
    assert aid not in sample.commercial_ledgers
    row = next(row for row in sample.pursuits if row["account_id"] == aid)
    _labeled(row)
    _labeled(row["component"])
    opportunity = row["opportunity"]
    _labeled(opportunity)
    _labeled(opportunity["scope_requirements"])
    _labeled(opportunity["qualification_evidence"])
    for collection in ("rfqs", "quotes", "quote_revisions", "quote_lines", "role_targets", "interactions"):
        for record in row[collection]:
            _labeled(record)
    for observation in opportunity["score_observations"]:
        _labeled(observation)
    for family in opportunity["scoring_inputs"].values():
        for record in family.values():
            _labeled(record)
    programs = {p.id: p for p in sample.programs}
    components = {c.id: c for c in sample.component_classes}
    assert opportunity["component_id"] in components
    assert components[opportunity["component_id"]].program_id == opportunity["program_id"]
    assert programs[opportunity["program_id"]].account_id == aid
    authored_canonical = [components[opportunity["component_id"]]]
    if aid not in EXISTING_PROGRAMS:
        authored_canonical.append(programs[opportunity["program_id"]])
    for canonical in authored_canonical:
        assert canonical.provenance.data_mode.value == "SAMPLE"
        assert canonical.provenance.synthetic is True
        assert canonical.provenance.source_url.startswith("sample://")
    assert opportunity["delivery_facility_id"] in {f.id for f in sample.btx_facilities}
    revisions = {revision["quote_revision_id"]: revision for revision in row["quote_revisions"]}
    quotes = {quote["quote_id"]: quote for quote in row["quotes"]}
    revision = revisions[opportunity["quote_revision_id"]]
    assert revision["quote_id"] in quotes
    assert all(line["component_id"] == opportunity["component_id"] for line in row["quote_lines"])


@pytest.mark.parametrize("aid", (*PURSUITS, *PRE_PURSUIT))
def test_named_prospect_fit_evidence_is_explicitly_simulated(sample, aid):
    account = next(account for account in sample.accounts if account.id == aid)
    assert set(account.prospect_fit_evidence) == {"target_cohort_match", "manufacturing_fit",
        "scale", "outsourcing_posture", "strategic_archetype", "existing_btx_access"}
    for record in account.prospect_fit_evidence.values():
        _labeled(record)
        assert record["provenance"]["truth_class"] == "POC_SCENARIO"
        assert all(url.startswith("sample://") for url in record["source_urls"])
    assert account.prospect_fit_evidence["scale"]["organization_ttm_revenue_usd"] > 0


def test_customer_overlay_preserves_preexisting_public_and_source_read_models(sample):
    original = build_sample_environment()
    for aid in CUSTOMERS:
        before = next(row for row in original.accounts if row.id == aid)
        after = next(row for row in sample.accounts if row.id == aid)
        assert after.public_identity == before.public_identity
        assert after.public_contacts == before.public_contacts
        assert set(after.business_units) >= set(before.business_units)
        for collection in ("crm_companies", "crm_contacts", "crm_deals", "crm_activities", "quotes", "orders"):
            before_ids = {row.id for row in getattr(original, collection) if row.account_id == aid}
            after_ids = {row.id for row in getattr(sample, collection)}
            assert before_ids <= after_ids
        assert aid in sample.rich_scenarios
        assert aid in sample.priority_scenarios
