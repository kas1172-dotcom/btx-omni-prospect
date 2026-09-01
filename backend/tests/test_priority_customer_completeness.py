from __future__ import annotations

from fastapi.testclient import TestClient

from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.providers.sample.environment import build_sample_environment

PRIORITY_IDS = {
    "honeywell",
    "boeing",
    "kla",
    "spacex",
    "intuitive-surgical",
    "lockheed-martin",
    "woodward",
    "northrop-grumman",
    "huxwrx",
    "eaton",
    "emerson",
}
REFERENCE_ONLY_PRIORITY = {"honeywell", "woodward", "huxwrx", "eaton", "emerson"}


def test_priority_cohort_has_one_explicit_bounded_completeness_scenario_each() -> None:
    sample = build_sample_environment()
    accounts = {item.id: item for item in sample.accounts}

    assert set(sample.priority_scenarios) == PRIORITY_IDS
    assert PRIORITY_IDS <= set(accounts)
    assert all(sample.priority_scenarios[item].reason_for_attention for item in PRIORITY_IDS)
    assert all(sample.priority_scenarios[item].recommended_next_step for item in PRIORITY_IDS)
    assert all(sample.priority_scenarios[item].scenario_intent for item in PRIORITY_IDS)
    assert all(any(facility.account_id == item for facility in sample.facilities) for item in PRIORITY_IDS)
    assert all(accounts[item].btx_top_100 for item in PRIORITY_IDS)


def test_reference_identity_stays_reference_while_sample_context_is_explicit() -> None:
    sample = build_sample_environment()
    accounts = {item.id: item for item in sample.accounts}
    priority_contexts = [
        item
        for item in sample.commercial_contexts
        if item.provenance.source_system == "priority-customer-sample"
    ]

    assert {item.account_id for item in priority_contexts} == {
        "honeywell",
        "woodward",
        "eaton",
        "emerson",
    }
    assert all(item.account_id in PRIORITY_IDS for item in priority_contexts)
    assert all(item.provenance.synthetic for item in priority_contexts)
    assert all(item.provenance.data_mode.value == "SAMPLE" for item in priority_contexts)
    assert all("SAMPLE commercial context" in item.jamie_validation_required[0] for item in priority_contexts)
    assert all(accounts[item].public_research_state == "SANITIZED_REFERENCE" for item in REFERENCE_ONLY_PRIORITY)
    assert not any(
        signal.account_name in {accounts[item].legal_name for item in REFERENCE_ONLY_PRIORITY}
        for signal in sample.intelligence_events
    )
    assert all(not accounts[item].public_contacts for item in REFERENCE_ONLY_PRIORITY)


def test_priority_scenarios_are_varied_and_alerts_remain_rule_generated() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(
        sample.commercial_contexts,
        sample.quotes,
        observed_at=PocRuntime.observed_at(),
        orders=sample.orders,
    )
    kinds = {(item.account_id, item.type.value) for item in alerts}
    accounts = {item.id: item for item in sample.accounts}

    assert accounts["honeywell"].relationship is AccountRelationship.CURRENT_CUSTOMER
    assert accounts["woodward"].relationship is AccountRelationship.FORMER_CUSTOMER
    assert accounts["huxwrx"].relationship is AccountRelationship.PROSPECT
    assert ("honeywell", "CROSS_BU_COORDINATION") in kinds
    assert ("woodward", "CUSTOMER_INACTIVITY") in kinds
    assert ("eaton", "BOOKINGS_DECLINE") in kinds
    assert not any(item.account_id == "huxwrx" for item in alerts)


def test_priority_scores_are_deterministic_inputs_not_hand_written_outputs() -> None:
    sample = build_sample_environment()
    assert PRIORITY_IDS <= set(sample.scoring_inputs)
    for account_id in PRIORITY_IDS:
        first = calculate_account_attractiveness(
            AccountAttractivenessInputs(sample.scoring_inputs[account_id]),
            evidence_ids=(f"sample-score:{account_id}",),
            calculated_at=PocRuntime.observed_at(),
        )
        second = calculate_account_attractiveness(
            AccountAttractivenessInputs(sample.scoring_inputs[account_id]),
            evidence_ids=(f"sample-score:{account_id}",),
            calculated_at=PocRuntime.observed_at(),
        )
        assert first == second
        assert first.score is not None
    assert calculate_account_attractiveness(
        AccountAttractivenessInputs(sample.scoring_inputs["huxwrx"]),
        evidence_ids=("sample-score:huxwrx",),
        calculated_at=PocRuntime.observed_at(),
    ).coverage < 0.5


def test_customer_api_exposes_rich_and_sparse_priority_truthfully() -> None:
    client = TestClient(create_app())
    listed = {item["id"]: item for item in client.get("/api/accounts").json()["accounts"]}
    honeywell = client.get("/api/accounts/honeywell").json()
    huxwrx = client.get("/api/accounts/huxwrx").json()

    assert honeywell["truth_categories"] == {
        "public": "SANITIZED_REFERENCE_SOURCE",
        "btx": "SIMULATED_BTX_CONTEXT",
    }
    assert len(honeywell["prism_commercial_context"]) == 2
    assert honeywell["alerts"]
    assert honeywell["intelligence"] == []
    assert honeywell["public_contacts"] == []
    assert huxwrx["truth_categories"] == {
        "public": "SANITIZED_REFERENCE_SOURCE",
        "btx": "SIMULATED_BTX_CONTEXT",
    }
    assert huxwrx["prism_commercial_context"] == []
    assert huxwrx["alerts"] == []
    assert huxwrx["account_attractiveness"]["status"] == "NEEDS_RESEARCH"
    assert huxwrx["account_attractiveness"]["score"] is None
    assert listed["huxwrx"]["attractiveness"] is None
    assert listed["huxwrx"]["account_attractiveness"]["score"] is None
    assert listed["honeywell"]["attractiveness"] == honeywell["account_attractiveness"]["score"]
    assert huxwrx["account_attractiveness"]["evidence_ids"] == []
    assert all(not factor["evidence_ids"] for factor in huxwrx["account_attractiveness"]["factors"])
    assert huxwrx["commercial_source_states"]["crm"]["source_state"] == "NO_LINKED_DATA"
    assert "No linked CRM company for this canonical Customer" in huxwrx["missingness"]


def test_reference_only_universe_does_not_receive_accidental_sample_context() -> None:
    sample = build_sample_environment()
    enriched = {
        item.account_id
        for item in sample.commercial_contexts
        if item.provenance.source_system == "priority-customer-sample"
    }
    untouched_reference = {
        item.id
        for item in sample.accounts
        if item.public_research_state == "SANITIZED_REFERENCE" and item.id not in PRIORITY_IDS
    }

    assert enriched <= PRIORITY_IDS
    assert not enriched & untouched_reference
    assert not any(item in sample.priority_scenarios for item in untouched_reference)
