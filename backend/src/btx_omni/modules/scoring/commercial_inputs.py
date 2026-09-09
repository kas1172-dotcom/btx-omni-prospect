"""Evidence-backed selections for the unchanged Account Attractiveness rubric."""
from datetime import date, timedelta

from btx_omni.modules.scoring.account_attractiveness import AccountAttractivenessInputs


def commercial_attractiveness_inputs(account: dict) -> AccountAttractivenessInputs:
    selections, evidence = {}, {}
    as_of = date.fromisoformat(account["as_of"])
    recognized = [r for r in account["revenue_events"] if r["revenue_minor"] > 0 and date.fromisoformat(r["recognized_date"]) <= as_of]
    active_months = {r["recognized_date"][:7] for r in recognized}
    if active_months:
        key = "program_durability.repeat_production_pattern"
        selections[key] = "ESTABLISHED_RECURRING" if len(active_months) >= 6 else "MULTIPLE_BATCHES_NOT_LOCKED" if len(active_months) >= 2 else "SINGLE_DEFINED_RUN"
        evidence[key] = tuple(r["revenue_event_id"] for r in recognized)
    orders = {r["order_id"]: r for r in account["orders"]}
    firm_open_lines = [line for line in account["order_lines"]
        if orders[line["order_id"]].get("accepted_quote_revision_id")
        and date.fromisoformat(orders[line["order_id"]]["ordered_date"]) <= as_of
        and line["quantity"] > sum(r["quantity"] for r in account["shipments"] if r["order_line_id"] == line["order_line_id"] and date.fromisoformat(r["shipped_date"]) <= as_of)
        + sum(r["quantity"] for r in account["cancellations"] if r["order_line_id"] == line["order_line_id"] and date.fromisoformat(r["date"]) <= as_of)]
    if firm_open_lines:
        key = "program_durability.commitment_strength"
        # Only firm, accepted release obligations; framework forecast is not a commitment.
        selections[key] = "FUNDED_AWARDED_CONTRACTED"
        evidence[key] = tuple(r["order_line_id"] for r in firm_open_lines)
    lines = {r["order_line_id"]: r for r in account["order_lines"]}
    recent = [r for r in account["revenue_events"] if r["revenue_minor"] > 0 and as_of - timedelta(days=90) <= date.fromisoformat(r["recognized_date"]) <= as_of]
    units = {lines[r["order_line_id"]]["business_unit_id"] for r in recent}
    if units:
        selections["btx_commercial_adjacency"] = "EXISTING_MULTI_BU_ACTIVE" if len(units) >= 2 else "EXISTING_ONE_BU_ACTIVE"
        evidence["btx_commercial_adjacency"] = tuple(r["revenue_event_id"] for r in recent)
        key = "addressable_btx_work.cross_bu_applicability"
        selections[key] = "TWO_PLUS_BU" if len(units) >= 2 else "ONE_BU"
        evidence[key] = tuple(r["revenue_event_id"] for r in recent)
    if active_months:
        key = "addressable_btx_work.make_buy_propensity"
        selections[key] = "SOURCES_EXTERNALLY"
        evidence[key] = tuple(r["revenue_event_id"] for r in recognized)
    return AccountAttractivenessInputs(selections, evidence)
