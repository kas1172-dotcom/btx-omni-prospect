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
RICH_JOINED_PRIORITY = {
    "boeing",
    "kla",
    "spacex",
    "intuitive-surgical",
    "lockheed-martin",
    "northrop-grumman",
}


def _priority_completeness(sample) -> dict[str, dict[str, bool]]:
    """Compact regression matrix; keep sparse scenarios explicit and truthful."""
    capability_bu_ids = {
        business_unit_id
        for capability in sample.capabilities
        for business_unit_id in capability.business_units
    }
    relationship_accounts = {
        account_id
        for edge in sample.relationship_edges
        for account_id in (edge.from_account_id, edge.to_account_id)
    }
    public_signal_accounts = {item.account_id for item in sample.public_signals}
    action_accounts = {
        item.account_id
        for item in CommercialAlertEngine().evaluate(
            sample.commercial_contexts,
            sample.quotes,
            observed_at=PocRuntime.observed_at(),
            orders=sample.orders,
        )
    }
    return {
        account_id: {
            "commercial": any(item.account_id == account_id for item in sample.commercial_contexts),
            "quote": any(item.account_id == account_id for item in sample.quotes),
            "order": any(item.account_id == account_id for item in sample.orders),
            "crm": any(item.account_id == account_id for item in sample.crm_companies),
            "program": (
                any(item.account_id == account_id for item in sample.programs)
                or any(item.account_id == account_id and item.program_id for item in sample.quotes)
                or any(item.account_id == account_id and item.program_id for item in sample.crm_deals)
            ),
            "component_capability": any(
                item.account_id == account_id
                and item.business_unit in capability_bu_ids
                and item.component_class_ids
                for item in sample.quotes
            ) or any(
                component.program_id in {
                    program.id for program in sample.programs if program.account_id == account_id
                }
                and set(component.business_unit_ids) & capability_bu_ids
                for component in sample.component_classes
            ),
            "facility": any(item.account_id == account_id for item in sample.facilities),
            "relationship": account_id in relationship_accounts,
            "scoring": account_id in sample.scoring_inputs,
            "intelligence": account_id in public_signal_accounts,
            "matching": any(item.account_id == account_id for item in sample.matching_components),
            "action_context": account_id in action_accounts,
        }
        for account_id in sample.priority_scenarios
    }


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


def test_priority_roster_proves_joined_sample_paths_without_filling_sparse_cases() -> None:
    sample = build_sample_environment()
    matrix = _priority_completeness(sample)
    accounts = {item.id: item for item in sample.accounts}
    program_ids = {item.id for item in sample.programs}
    component_ids = {item.id for item in sample.component_classes}
    business_unit_ids = {item.id for item in sample.business_units}
    quote_ids = {item.id for item in sample.quotes}
    company_ids = {item.id for item in sample.crm_companies}

    assert set(matrix) == PRIORITY_IDS
    assert all(matrix[account_id]["facility"] for account_id in PRIORITY_IDS)
    assert all(matrix[account_id]["matching"] for account_id in RICH_JOINED_PRIORITY)
    assert all(
        matrix[account_id]["commercial"]
        and matrix[account_id]["quote"]
        and matrix[account_id]["order"]
        and matrix[account_id]["crm"]
        and matrix[account_id]["program"]
        and matrix[account_id]["component_capability"]
        and matrix[account_id]["relationship"]
        and matrix[account_id]["scoring"]
        for account_id in RICH_JOINED_PRIORITY
    )
    assert {
        account_id
        for account_id in RICH_JOINED_PRIORITY
        if matrix[account_id]["intelligence"]
    } == {"boeing", "lockheed-martin", "northrop-grumman"}
    assert matrix["huxwrx"] == {
        "commercial": False, "quote": False, "order": False, "crm": False,
        "program": True, "component_capability": True, "facility": True,
        "relationship": False, "scoring": True, "intelligence": False,
        "matching": False, "action_context": False,
    }
    assert RICH_JOINED_PRIORITY <= {
        account_id for account_id, values in matrix.items() if values["action_context"]
    }
    assert {"honeywell", "woodward", "eaton"} <= {
        account_id for account_id, values in matrix.items() if values["action_context"]
    }
    huxwrx_program = next(item for item in sample.programs if item.id == "huxwrx-sample-opportunity")
    huxwrx_component = next(item for item in sample.component_classes if item.id == "cc-huxwrx-sample-opportunity")
    assert huxwrx_program.account_id == "huxwrx"
    assert huxwrx_component.program_id == huxwrx_program.id
    assert huxwrx_component.business_unit_ids == ("era-industries",)
    assert huxwrx_program.provenance.data_mode.value == "SAMPLE"
    assert huxwrx_program.provenance.synthetic
    assert {item.account_id for item in sample.commercial_contexts} <= set(accounts)
    assert {item.business_unit for item in sample.commercial_contexts} <= business_unit_ids
    assert {item.canonical_account_id for item in sample.paperless_accounts} <= set(accounts)
    assert {item.account_id for item in sample.quotes} <= set(accounts)
    assert {item.business_unit for item in sample.quotes} <= business_unit_ids
    assert {item.program_id for item in sample.quotes} <= program_ids
    assert {component_id for item in sample.quotes for component_id in item.component_class_ids} <= component_ids
    assert {item.account_id for item in sample.orders} <= set(accounts)
    assert {item.business_unit_id for item in sample.orders} <= business_unit_ids
    assert {item.program_id for item in sample.orders if item.program_id} <= program_ids
    assert {item.quote_id for item in sample.orders if item.quote_id} <= quote_ids
    assert {item.account_id for item in sample.crm_companies} <= set(accounts)
    assert {item.company_id for item in sample.crm_contacts} <= company_ids
    assert {item.company_id for item in sample.crm_deals} <= company_ids
    assert {item.company_id for item in sample.crm_activities} <= company_ids
    assert {item.business_unit for item in sample.crm_deals if item.business_unit} <= business_unit_ids
    assert {item.program_id for item in sample.crm_deals if item.program_id} <= program_ids
    assert {item.account_id for item in sample.programs if item.account_id} <= set(accounts)
    assert {item.account_id for item in sample.facilities} <= set(accounts)
    assert {item.from_account_id for item in sample.relationship_edges} <= set(accounts)
    assert {item.to_account_id for item in sample.relationship_edges} <= set(accounts)
    assert {item.program_id for item in sample.relationship_edges if item.program_id} <= program_ids


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
