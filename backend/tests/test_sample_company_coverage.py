"""Named-company SAMPLE templates: customer, scoped pursuit, and pre-pursuit."""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import Response

from btx_omni.api.commercial import opportunity_workspace
from btx_omni.modules.classification.commercial_adjacency import classify_commercial_adjacency
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.modules.commercial.opportunities import account_opportunities
from btx_omni.modules.scoring.account_attractiveness import FACTORS
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.scoring.prospect_fit import prospect_fit_projection
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.named_company_cases import CUSTOMERS, PRE_PURSUIT, PURSUITS


@pytest.fixture(scope="module")
def sample():
    return enhance_environment(build_sample_environment())


@pytest.mark.parametrize("aid", tuple(CUSTOMERS))
def test_named_customers_have_reconciled_ledgers_and_numeric_scores(sample, aid):
    ledger = sample.commercial_ledgers[aid]
    assert len(ledger["monthly_commercial_history"]) == 12
    assert validate_commercial_account(ledger)["orders"] >= 4
    months = ledger["monthly_commercial_history"]
    assert sum(row["bookings_minor"] for row in months[-3:]) > sum(
        row["bookings_minor"] for row in months[-6:-3])
    decisions = customer_decisions(ledger, account_id=aid, revision=sample.commercial_revision,
        current_customer=True, facility_ids=frozenset(f.id for f in sample.btx_facilities))
    for family in ("customer_health", "internal_commercial_risk"):
        assert decisions[family]["score"] is not None
        assert decisions[family]["band"]
    pursuits = account_opportunities(sample, aid)
    assert len(pursuits) == 1
    assert pursuits[0]["opportunity_priority"]["score"] is not None
    assert pursuits[0]["pwin"]["score"] is not None
    assert pursuits[0]["delivery_feasibility"]["score"] is not None


@pytest.mark.parametrize("aid", tuple(PURSUITS))
def test_named_prospect_pursuits_have_fit_and_numeric_opportunity_without_ledger(sample, aid):
    assert aid not in sample.commercial_ledgers
    account = next(row for row in sample.accounts if row.id == aid)
    fit = prospect_fit_projection(account, applicable=True, as_of=date(2026, 9, 20))
    assert fit.score is not None and fit.status == "AVAILABLE"
    rows = account_opportunities(sample, aid)
    assert len(rows) == 1 and rows[0]["lane"] == "PROSPECT"
    for family in ("opportunity_priority", "pwin", "delivery_feasibility"):
        assert rows[0][family]["score"] is not None
    pursuit = next(row for row in sample.pursuits if row["account_id"] == aid)
    adjacency = next(row for row in pursuit["opportunity"]["score_observations"]
                     if row["path"] == "btx_commercial_adjacency")
    assert adjacency["bin"] == "COLD_PROSPECT"
    # No durable or in-memory commercial ledger means customer-only families
    # are not applicable, never a fabricated zero-valued assessment.
    assert aid not in sample.commercial_ledgers


def test_unknown_no_ledger_relationship_does_not_default_to_cold(sample):
    pursuit = next(row for row in sample.pursuits if row["account_id"] == "ge-aerospace")
    context = {"order_lines": [], "revenue_events": [], "monthly_commercial_history": [],
               "quote_revisions": pursuit["quote_revisions"], "quotes": pursuit["quotes"]}
    result = classify_commercial_adjacency(context, pursuit["opportunity"], as_of=pursuit["as_of"])
    assert result.state == "MISSING" and result.bin_value is None


def test_sample_workspace_includes_parallel_pursuits_without_prospect_ledgers(sample):
    runtime = SimpleNamespace(environment=lambda: sample,
                              settings=SimpleNamespace(data_mode="SAMPLE"))
    rows = opportunity_workspace(Response(), actor=None, runtime=runtime)["opportunities"]
    ids = {row["account_id"] for row in rows}
    assert set(PURSUITS) <= ids
    assert set(PRE_PURSUIT).isdisjoint(ids)
    assert all(aid not in sample.commercial_ledgers for aid in PURSUITS)
    runtime.settings.data_mode = "CONNECTED"
    connected_ids = {row["account_id"] for row in
                     opportunity_workspace(Response(), actor=None, runtime=runtime)["opportunities"]}
    assert set(PURSUITS).isdisjoint(connected_ids)


@pytest.mark.parametrize("aid", PRE_PURSUIT)
def test_named_pre_pursuit_prospect_has_fit_but_no_opportunity(sample, aid):
    assert aid not in sample.commercial_ledgers
    account = next(row for row in sample.accounts if row.id == aid)
    fit = prospect_fit_projection(account, applicable=True, as_of=date(2026, 9, 20))
    assert fit.score is not None and fit.status == "AVAILABLE"
    assert account_opportunities(sample, aid) == []
    assert not any(row["account_id"] == aid for row in sample.pursuits)


@pytest.mark.parametrize("aid", (*CUSTOMERS, *PURSUITS))
def test_named_opportunities_have_one_classification_per_leaf(sample, aid):
    opportunity = (sample.commercial_ledgers[aid]["opportunities"][0] if aid in CUSTOMERS
                   else next(row["opportunity"] for row in sample.pursuits if row["account_id"] == aid))
    observations = opportunity["score_observations"]
    paths = [row["path"] for row in observations]
    expected_paths = {
        factor.key + "." + leaf.rubric.key
        for factor in FACTORS for leaf in factor.subfactors
    } | {factor.key for factor in FACTORS if factor.single_rubric is not None}
    assert len(paths) == len(set(paths)) == 18
    assert set(paths) == expected_paths
    path_a = {"program_durability.expected_production_horizon",
        "btx_commercial_adjacency", "addressable_btx_work.cross_bu_applicability",
        "addressable_btx_work.btx_relevant_component_content",
        "btx_manufacturing_fit.material_match", "btx_manufacturing_fit.process_tolerance_match",
        "btx_manufacturing_fit.certification_compliance_fit",
        "btx_manufacturing_fit.volume_compatibility"}
    for row in observations:
        assert row["classification"]["method"] == (
            "DETERMINISTIC" if row["path"] in path_a else "SYNTHETIC_AUTHORED")
    delivery = opportunity["scoring_inputs"]["delivery_feasibility"]
    for factor in ("capability_match", "schedule_feasibility", "quality_certification"):
        assert delivery[factor]["classification"]["method"] == "DETERMINISTIC"
    for factor in ("material_readiness", "margin", "coordination"):
        assert delivery[factor]["classification"]["method"] == "SYNTHETIC_AUTHORED"
