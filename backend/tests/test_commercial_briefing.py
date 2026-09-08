from btx_omni.modules.commercial.briefing import commercial_briefing


def test_briefing_uses_selected_case_and_keeps_role_distinct_from_assigned_user():
    account = {
        "as_of": "2026-08-31", "currency": "USD",
        "service_events": [{"service_event_id": "case", "opened_date": "2026-08-20", "title": "Cleaning scope changed", "details": "Compare the revised cleaning cost with the prior quote.", "related_record_ids": ["opportunity"]}],
        "actions": [{"action_id": "proposal", "case_id": "case", "title": "Review the two cleaning options", "owner_role_id": "engineering-role", "due_date": "2026-09-09", "evidence_record_ids": ["quote-r1", "quote-r2"]}],
        "components": [{"component_id": "component", "name": "Distinct inspection enclosure"}],
        "opportunities": [{"opportunity_id": "opportunity", "component_id": "component", "value_minor": 1200}],
        "order_lines": [],
        "shipments": [],
    }
    result = commercial_briefing(account, canonical_account_id="kla", revision="r1")
    assert result["summary"] == "Cleaning scope changed"
    assert result["next_action"] == "Review the two cleaning options"
    assert result["assigned_owner_id"] is None
    assert result["work_status"] == "PROPOSAL_NOT_CREATED_WORK"
    assert result["opportunity_value_minor"] == 1200
    assert "quote-r2" in result["evidence_ids"]
    assert result["fulfillment"] is None


def test_briefing_reconciles_partial_fulfillment_in_integer_minor_units():
    account = {
        "as_of": "2026-08-31",
        "currency": "USD",
        "service_events": [{
            "service_event_id": "case",
            "opened_date": "2026-08-28",
            "title": "Latest release is partly shipped",
            "details": "Agree a recovery plan.",
            "related_record_ids": ["line-1", "shipment-1"],
        }],
        "actions": [],
        "components": [],
        "opportunities": [],
        "order_lines": [{
            "order_line_id": "line-1",
            "quantity": 292,
            "line_total_minor": 28_616_000,
            "currency": "USD",
            "committed_date": "2026-08-24",
        }],
        "shipments": [{
            "shipment_id": "shipment-1",
            "order_line_id": "line-1",
            "quantity": 146,
            "value_minor": 14_308_000,
            "shipped_date": "2026-08-24",
        }],
    }

    fulfillment = commercial_briefing(account, canonical_account_id="boeing", revision="r1")["fulfillment"]

    assert fulfillment == {
        "state": "PARTIALLY_SHIPPED",
        "order_line_id": "line-1",
        "ordered_quantity": 292,
        "shipped_quantity": 146,
        "remaining_quantity": 146,
        "order_value_minor": 28_616_000,
        "shipped_value_minor": 14_308_000,
        "currency": "USD",
        "committed_date": "2026-08-24",
        "latest_shipped_date": "2026-08-24",
        "evidence_ids": ["line-1", "shipment-1"],
    }


def test_briefing_rejects_shipped_quantity_above_ordered_quantity():
    account = {
        "as_of": "2026-08-31",
        "currency": "USD",
        "service_events": [{"service_event_id": "case", "opened_date": "2026-08-28", "title": "Mismatch", "details": "Review.", "related_record_ids": ["line-1", "shipment-1"]}],
        "actions": [], "components": [], "opportunities": [],
        "order_lines": [{"order_line_id": "line-1", "quantity": 1, "line_total_minor": 100, "currency": "USD"}],
        "shipments": [{"shipment_id": "shipment-1", "order_line_id": "line-1", "quantity": 2, "value_minor": 200}],
    }

    import pytest

    with pytest.raises(ValueError, match="exceeds ordered quantity"):
        commercial_briefing(account, canonical_account_id="boeing", revision="r1")
