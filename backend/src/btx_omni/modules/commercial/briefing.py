"""Concise record-specific commercial briefing; no invented supply or outreach."""


def _fulfillment_summary(account: dict, case: dict | None) -> dict | None:
    if not case:
        return None
    related = set(case.get("related_record_ids", []))
    order_line = next(
        (row for row in account.get("order_lines", []) if row.get("order_line_id") in related),
        None,
    )
    if not order_line:
        return None
    shipments = [
        row
        for row in account.get("shipments", [])
        if row.get("shipment_id") in related
        or row.get("order_line_id") == order_line["order_line_id"]
    ]
    shipped_quantity = sum(int(row.get("quantity", 0)) for row in shipments)
    ordered_quantity = int(order_line["quantity"])
    remaining_quantity = ordered_quantity - shipped_quantity
    if remaining_quantity < 0:
        raise ValueError(
            f"Shipment quantity exceeds ordered quantity for {order_line['order_line_id']}"
        )
    shipped_value_minor = sum(int(row.get("value_minor", 0)) for row in shipments)
    return {
        "state": "FULFILLED" if remaining_quantity == 0 else "PARTIALLY_SHIPPED" if shipped_quantity else "NOT_SHIPPED",
        "order_line_id": order_line["order_line_id"],
        "ordered_quantity": ordered_quantity,
        "shipped_quantity": shipped_quantity,
        "remaining_quantity": remaining_quantity,
        "order_value_minor": int(order_line["line_total_minor"]),
        "shipped_value_minor": shipped_value_minor,
        "currency": order_line.get("currency", account["currency"]),
        "committed_date": order_line.get("committed_date"),
        "latest_shipped_date": max(
            (row.get("shipped_date") for row in shipments if row.get("shipped_date")),
            default=None,
        ),
        "evidence_ids": [order_line["order_line_id"], *[row["shipment_id"] for row in shipments]],
    }


def commercial_briefing(account: dict, *, canonical_account_id: str, revision: str) -> dict:
    cases = sorted(account["service_events"], key=lambda r: (r.get("updated_date", r["opened_date"]), r["service_event_id"]), reverse=True)
    actions = sorted(account["actions"], key=lambda r: (r.get("due_date") or "9999", r["action_id"]))
    case = cases[0] if cases else None
    action = next((r for r in actions if case and r.get("case_id") == case["service_event_id"]), actions[0] if actions else None)
    component_names = {r["component_id"]: r["name"] for r in account["components"]}
    opportunity = next((r for r in account["opportunities"] if case and r["opportunity_id"] in case.get("related_record_ids", [])), None)
    fulfillment = _fulfillment_summary(account, case)
    return {
        "id": f"commercial-brief:{canonical_account_id}", "revision": revision,
        "account_id": canonical_account_id, "as_of": account["as_of"],
        "expansion_context": account.get('expansion_brief'),
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
        "fulfillment": fulfillment,
        "evidence_ids": list(dict.fromkeys([
            *([case["service_event_id"], *case.get("related_record_ids", [])] if case else []),
            *(action.get("evidence_record_ids", []) if action else []),
        ])),
        "prerequisites": ["Assign an accountable user before execution.", "Verify recipient and scope before any external proposal."],
    }
