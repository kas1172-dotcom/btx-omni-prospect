"""Concise record-specific commercial briefing; no invented supply or outreach."""
def commercial_briefing(account: dict, *, canonical_account_id: str, revision: str) -> dict:
    cases = sorted(account["service_events"], key=lambda r: (r.get("updated_date", r["opened_date"]), r["service_event_id"]), reverse=True)
    actions = sorted(account["actions"], key=lambda r: (r.get("due_date") or "9999", r["action_id"]))
    case = cases[0] if cases else None
    action = next((r for r in actions if case and r.get("case_id") == case["service_event_id"]), actions[0] if actions else None)
    component_names = {r["component_id"]: r["name"] for r in account["components"]}
    opportunity = next((r for r in account["opportunities"] if case and r["opportunity_id"] in case.get("related_record_ids", [])), None)
    return {
        "id": f"commercial-brief:{canonical_account_id}", "revision": revision,
        "account_id": canonical_account_id, "as_of": account["as_of"],
        "summary": case["title"] if case else "Review the linked commercial history.",
        "explanation": case["details"] if case else None,
        "component": component_names.get(opportunity["component_id"]) if opportunity else None,
        "opportunity_id": opportunity["opportunity_id"] if opportunity else None,
        "opportunity_value_minor": opportunity["value_minor"] if opportunity else None,
        "currency": account["currency"],
        "next_action": action["title"] if action else "Review the scoped records before proposing a follow-up.",
        "due_date": action.get("due_date") if action else None,
        "owner_role_id": action.get("owner_role_id") if action else None,
        "assigned_owner_id": None,
        "source_action_id": action["action_id"] if action else None,
        "work_status": "PROPOSAL_NOT_CREATED_WORK",
        "evidence_ids": list(dict.fromkeys([
            *([case["service_event_id"], *case.get("related_record_ids", [])] if case else []),
            *(action.get("evidence_record_ids", []) if action else []),
        ])),
        "prerequisites": ["Assign an accountable user before execution.", "Verify recipient and scope before any external proposal."],
    }
