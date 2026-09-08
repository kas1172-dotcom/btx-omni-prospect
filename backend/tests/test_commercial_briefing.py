from btx_omni.modules.commercial.briefing import commercial_briefing


def test_briefing_uses_selected_case_and_keeps_role_distinct_from_assigned_user():
    account = {
        "as_of": "2026-08-31", "currency": "USD",
        "service_events": [{"service_event_id": "case", "opened_date": "2026-08-20", "title": "Cleaning scope changed", "details": "Compare the revised cleaning cost with the prior quote.", "related_record_ids": ["opportunity"]}],
        "actions": [{"action_id": "proposal", "case_id": "case", "title": "Review the two cleaning options", "owner_role_id": "engineering-role", "due_date": "2026-09-09", "evidence_record_ids": ["quote-r1", "quote-r2"]}],
        "components": [{"component_id": "component", "name": "Distinct inspection enclosure"}],
        "opportunities": [{"opportunity_id": "opportunity", "component_id": "component", "value_minor": 1200}],
    }
    result = commercial_briefing(account, canonical_account_id="kla", revision="r1")
    assert result["summary"] == "Cleaning scope changed"
    assert result["next_action"] == "Review the two cleaning options"
    assert result["assigned_owner_id"] is None
    assert result["work_status"] == "PROPOSAL_NOT_CREATED_WORK"
    assert result["opportunity_value_minor"] == 1200
    assert "quote-r2" in result["evidence_ids"]
