"""One canonical lifecycle calculation for cards, routes, actions and Omni tools."""
from datetime import date


def fulfillment_state(account: dict, *, canonical_account_id: str, revision: str, as_of: date | None = None) -> dict:
    snapshot_date = date.fromisoformat(account["as_of"])
    as_of = min(as_of, snapshot_date) if as_of else snapshot_date
    orders = {row['order_id']: row for row in account['orders']}
    omitted_undated_plans = 0
    lines = []
    for line in sorted(account["order_lines"], key=lambda row: row["order_line_id"]):
        if date.fromisoformat(orders[line['order_id']]['ordered_date']) > as_of:
            continue
        lid = line["order_line_id"]
        shipments = [r for r in account["shipments"] if r["order_line_id"] == lid and date.fromisoformat(r["shipped_date"]) <= as_of]
        shipment_ids = {r["shipment_id"] for r in shipments}
        cancellations = [r for r in account["cancellations"] if r["order_line_id"] == lid and date.fromisoformat(r["date"]) <= as_of]
        acceptances = [r for r in account["acceptances"] if r["shipment_id"] in shipment_ids and date.fromisoformat(r["accepted_date"]) <= as_of]
        accepted_ids = {r["acceptance_id"] for r in acceptances}
        revenues = [r for r in account["revenue_events"] if r["acceptance_id"] in accepted_ids and date.fromisoformat(r["recognized_date"]) <= as_of]
        shipped = sum(r["quantity"] for r in shipments)
        cancelled = sum(r["quantity"] for r in cancellations)
        accepted = sum(r["quantity"] for r in acceptances)
        # Valuation is deterministic and remains distinct from recognized revenue.
        # A partial acceptance uses the exact order-line price, not model arithmetic.
        unaccepted_value_minor = (shipped - accepted) * line['unit_price_minor']
        remaining = line["quantity"] - shipped - cancelled
        committed = date.fromisoformat(line["committed_date"]) if line.get("committed_date") else None
        overdue = remaining > 0 and committed is not None and committed < as_of
        plans = []
        for plan in account['fulfillment_plans']:
            if plan['order_line_id'] != lid:
                continue
            effective = plan.get('effective_date')
            # Authorship and proposed dispatch dates are not plan-effective dates.
            if effective and date.fromisoformat(effective) > as_of:
                continue
            if not effective and as_of < snapshot_date:
                omitted_undated_plans += 1
                continue
            plans.append(plan)
        constraints = []
        if overdue:
            constraints.append({"id": f"constraint:{lid}:missed-commitment", "type": "MISSED_COMMITMENT", "scope": {"order_line_id": lid, "component_id": line["component_id"], "program_id": line["program_id"], "business_unit_id": line["business_unit_id"]}, "evidence_ids": [lid, *sorted(shipment_ids)], "reason": f"{remaining} units remain against the {committed.isoformat()} commitment.", "blocks": "REPEAT_OR_CONFIRM_EXISTING_COMMITMENT"})
        for plan in plans:
            if not plan["buyer_accepted"]:
                constraints.append({"id": f"constraint:{plan['plan_id']}:buyer-acceptance", "type": "UNACCEPTED_RECOVERY_PROPOSAL", "scope": {"order_line_id": lid}, "evidence_ids": [plan["plan_id"]], "reason": f"The proposed {plan['proposed_ship_date']} dispatch has not been accepted by the buyer.", "blocks": "PRESENT_PROPOSAL_AS_ACCEPTED"})
        lines.append({"order_line_id": lid, "order_id": line["order_id"], "component_id": line["component_id"], "program_id": line["program_id"], "business_unit_id": line["business_unit_id"],
                      "ordered_quantity": line["quantity"], "shipped_quantity": shipped,
                      "cancelled_quantity": cancelled, "accepted_quantity": accepted,
                      "remaining_quantity": remaining, "shipped_unaccepted_quantity": shipped - accepted,
                      "shipped_unaccepted_value_minor": unaccepted_value_minor,
                      "currency": line.get('currency', account['currency']),
                      "shipments": [{**shipment, 'accepted_quantity': sum(a['quantity'] for a in acceptances if a['shipment_id'] == shipment['shipment_id']),
                                     'unaccepted_value_minor': (shipment['quantity'] - sum(a['quantity'] for a in acceptances if a['shipment_id'] == shipment['shipment_id'])) * line['unit_price_minor']}
                                    for shipment in shipments],
                      "recognized_revenue_minor": sum(r["revenue_minor"] for r in revenues),
                      "committed_date": line.get("committed_date"), "overdue": overdue,
                      "plans": plans, "constraints": constraints,
                      "execution_status": "BLOCKED" if overdue else "NEEDS_CHECK" if remaining or shipped > accepted else "HISTORICAL_EXPERIENCE" if accepted else "CANCELLED",
                      "next_action": "Agree a recovery plan with operations and obtain buyer acceptance." if overdue else "Confirm scoped capacity, qualification and the buyer requirement before a new commitment." if remaining else "Verify outstanding acceptance; shipment alone is not recognized revenue." if shipped > accepted else "Review accepted work as historical experience; it does not establish spare capacity." if accepted else "Review the cancellation reason before considering new work.",
                      "evidence_ids": [lid, *sorted(shipment_ids), *sorted(accepted_ids), *(r["revenue_event_id"] for r in revenues)]})
    return {"account_id": canonical_account_id, "as_of": as_of.isoformat(), "snapshot_as_of": snapshot_date.isoformat(), "revision": revision,
            "temporal_limits": {"undated_plans_excluded_from_historical_query": omitted_undated_plans,
                                "plan_date_policy": "Undated plans describe the recorded snapshot only; authorship and proposed dispatch are not effective dates."},
            "currency": account["currency"], "lines": lines,
            "constraints": [constraint for line in lines for constraint in line["constraints"]],
            "open_line_count": sum(line["remaining_quantity"] > 0 for line in lines),
            "overdue_line_count": sum(line["overdue"] for line in lines),
            "recorded_history_totals": {key: sum(line[key] for line in lines) for key in (
                "ordered_quantity", "shipped_quantity", "cancelled_quantity", "accepted_quantity",
                "remaining_quantity", "shipped_unaccepted_quantity", "shipped_unaccepted_value_minor", "recognized_revenue_minor")},
            "totals_scope": "All recorded order-line history through the demo as-of, including opening history; not automatically the TTM reporting window.",
            "policy": "BTX_FULFILLMENT_POC_1; proposed dates do not replace committed dates; shipment is not acceptance or revenue."}
