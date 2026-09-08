"""Validate source-shaped commercial facts before canonical persistence.

This boundary performs arithmetic, not scoring or public-fact verification. Public
events are owned by Monitor and cannot enter through a commercial import.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any


class CommercialIntegrityError(ValueError):
    """A source record cannot be reconciled without inventing or losing facts."""


KEYS = {
    "programs": "program_id", "components": "component_id",
    "role_targets": "role_target_id", "rfqs": "rfq_id", "quotes": "quote_id",
    "quote_revisions": "quote_revision_id", "quote_lines": "quote_line_id",
    "agreements": "agreement_id", "orders": "order_id", "order_lines": "order_line_id",
    "cancellations": "cancellation_id", "shipments": "shipment_id",
    "acceptances": "acceptance_id", "revenue_events": "revenue_event_id",
    "invoices": "invoice_id", "payments": "payment_id",
    "service_events": "service_event_id", "interactions": "interaction_id",
    "opportunities": "opportunity_id", "actions": "action_id",
    "monthly_commercial_history": "snapshot_id", "fulfillment_plans": "plan_id",
}


def _require(ok: bool, locator: str, message: str) -> None:
    if not ok:
        raise CommercialIntegrityError(f"{locator}: {message}")


def _integer(value: Any, locator: str) -> int:
    _require(type(value) is int and value >= 0, locator, "requires nonnegative integer units")
    return value


def validate_commercial_account(account: dict[str, Any]) -> dict[str, int]:
    """Reconcile every transaction and every month; never silently drop rows."""
    aid = account["account_id"]
    _require(not account.get("public_events"), aid, "public events belong to Monitor")
    currency = account["currency"]
    _require(isinstance(currency, str) and len(currency) == 3, aid, "currency required")
    as_of = date.fromisoformat(account["as_of"])
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    for collection, key in KEYS.items():
        rows = account[collection]
        table = {r[key]: r for r in rows}
        _require(len(table) == len(rows), collection, "duplicate record identity")
        tables[collection] = table
        for rid, row in table.items():
            _require(isinstance(rid, str) and bool(rid), collection, "empty identity")
            _require(row.get("currency", currency) == currency, rid, "mixed currency")
            _require(row.get("account_id", aid) == aid, rid, "cross-account record")
            for field, value in row.items():
                if (field.endswith("_minor") or field == "quantity") and value is not None:
                    _integer(value, f"{rid}/{field}")

    def ref(collection: str, identity: str) -> dict[str, Any]:
        _require(identity in tables[collection], str(identity), f"missing {collection} reference")
        return tables[collection][identity]

    def dated(value: str) -> date:
        return date.fromisoformat(value)

    for collection in ("quote_lines", "order_lines"):
        for rid, row in tables[collection].items():
            ref("components", row["component_id"])
            _require(row["quantity"] * row["unit_price_minor"] == row["line_total_minor"], rid, "line total mismatch")
    for rid, row in tables["quote_revisions"].items():
        ref("quotes", row["quote_id"])
        lines = [ref("quote_lines", key) for key in row["line_ids"]]
        _require(len(set(row["line_ids"])) == len(lines), rid, "duplicate line reference")
        _require(all(line["quote_revision_id"] == rid for line in lines), rid, "line belongs to another revision")
        _require(sum(line["line_total_minor"] for line in lines) == row["total_minor"], rid, "revision total mismatch")
        if row["supersedes_revision_id"]:
            prior = ref("quote_revisions", row["supersedes_revision_id"])
            _require(prior["quote_id"] == row["quote_id"] and prior["revision_number"] < row["revision_number"], rid, "invalid superseded revision")
    for rid, row in tables["quotes"].items():
        ref("rfqs", row["rfq_id"])
        _require(ref("quote_revisions", row["current_revision_id"])["quote_id"] == rid, rid, "wrong current revision")
    for rid, row in tables["orders"].items():
        revision = ref("quote_revisions", row["accepted_quote_revision_id"])
        _require(revision["quote_id"] == row["quote_id"], rid, "accepted revision belongs to another quote")
        _require(dated(revision["issued_date"]) <= dated(row["ordered_date"]) <= as_of, rid, "invalid order date")
        lines = [ref("order_lines", key) for key in row["line_ids"]]
        _require(len(set(row["line_ids"])) == len(lines), rid, "duplicate order line")
        _require(all(line["order_id"] == rid for line in lines), rid, "wrong order line owner")
        _require(sum(line["line_total_minor"] for line in lines) == row["total_minor"], rid, "order total mismatch")
        if row["agreement_id"]:
            agreement = ref("agreements", row["agreement_id"])
            _require(agreement["accepted_revision_id"] == row["accepted_quote_revision_id"], rid, "agreement revision mismatch")
    shipped: dict[str, int] = defaultdict(int)
    cancelled: dict[str, int] = defaultdict(int)
    accepted: dict[str, int] = defaultdict(int)
    paid: dict[str, int] = defaultdict(int)
    for rid, row in tables["cancellations"].items():
        line = ref("order_lines", row["order_line_id"])
        cancelled[row["order_line_id"]] += row["quantity"]
        _require(row["value_minor"] == row["quantity"] * line["unit_price_minor"], rid, "cancellation value mismatch")
    for rid, row in tables["shipments"].items():
        line = ref("order_lines", row["order_line_id"])
        order = ref("orders", line["order_id"])
        shipped[row["order_line_id"]] += row["quantity"]
        _require(row["value_minor"] == row["quantity"] * line["unit_price_minor"], rid, "shipment value mismatch")
        _require(dated(order["ordered_date"]) <= dated(row["shipped_date"]) <= as_of, rid, "invalid shipment date")
    for rid, line in tables["order_lines"].items():
        ref("orders", line["order_id"])
        _require(shipped[rid] + cancelled[rid] <= line["quantity"], rid, "over-shipped or over-cancelled")
    for rid, row in tables["acceptances"].items():
        shipment = ref("shipments", row["shipment_id"])
        accepted[row["shipment_id"]] += row["quantity"]
        _require(dated(shipment["shipped_date"]) <= dated(row["accepted_date"]) <= as_of, rid, "invalid acceptance date")
        _require(accepted[row["shipment_id"]] <= shipment["quantity"], rid, "over-accepted")
    recognized: set[str] = set()
    for rid, row in tables["revenue_events"].items():
        acceptance = ref("acceptances", row["acceptance_id"])
        shipment = ref("shipments", acceptance["shipment_id"])
        line = ref("order_lines", row["order_line_id"])
        _require(row["acceptance_id"] not in recognized, rid, "duplicate recognition")
        recognized.add(row["acceptance_id"])
        _require(shipment["order_line_id"] == row["order_line_id"], rid, "wrong recognized order line")
        _require(row["quantity"] == acceptance["quantity"] and row["recognized_date"] == acceptance["accepted_date"], rid, "recognition must follow acceptance")
        _require(row["revenue_minor"] == row["quantity"] * line["unit_price_minor"], rid, "revenue mismatch")
        _require(row["cost_minor"] == row["quantity"] * line["unit_cost_minor"], rid, "cost mismatch")
    for rid, row in tables["invoices"].items():
        revenue = ref("revenue_events", row["revenue_event_id"])
        _require(row["amount_minor"] == revenue["revenue_minor"], rid, "invoice mismatch")
        _require(dated(revenue["recognized_date"]) <= dated(row["invoice_date"]) <= as_of, rid, "invalid invoice date")
    for rid, row in tables["payments"].items():
        invoice = ref("invoices", row["invoice_id"])
        paid[row["invoice_id"]] += row["amount_minor"]
        _require(dated(invoice["invoice_date"]) <= dated(row["paid_date"]) <= as_of, rid, "invalid payment date")
        _require(paid[row["invoice_id"]] <= invoice["amount_minor"], rid, "overpayment")
    months = sorted(account["monthly_commercial_history"], key=lambda r: r["period"])
    _require(len({m["period"] for m in months}) == len(months), aid, "duplicate month")
    for i, month in enumerate(months):
        period = month["period"]
        _require(month["opening_backlog_minor"] + month["bookings_minor"] - month["cancellations_minor"] - month["shipments_minor"] == month["closing_backlog_minor"], period, "backlog mismatch")
        if i:
            _require(months[i-1]["closing_backlog_minor"] == month["opening_backlog_minor"], period, "backlog discontinuity")
        for collection, day, value, target in (
            ("orders", "ordered_date", "total_minor", "bookings_minor"),
            ("shipments", "shipped_date", "value_minor", "shipments_minor"),
            ("cancellations", "date", "value_minor", "cancellations_minor"),
            ("revenue_events", "recognized_date", "revenue_minor", "revenue_minor"),
            ("revenue_events", "recognized_date", "cost_minor", "cost_of_revenue_minor"),
        ):
            amount = sum(r[value] for r in tables[collection].values() if r[day].startswith(period))
            _require(amount == month[target], period, f"{target} not reconciled to records")
        for field in ("revenue_minor", "bookings_minor", "shipments_minor"):
            _require(sum(r[field] for r in month["business_unit_allocations"]) == month[field], period, f"{field} BU allocation mismatch")
    ttm = account["ttm_summary"]
    for field in ("revenue_minor", "bookings_minor", "shipments_minor", "cancellations_minor", "cost_of_revenue_minor"):
        _require(sum(m[field] for m in months) == ttm[field], aid, f"TTM {field} mismatch")
    _require(ttm["gross_margin_minor"] == ttm["revenue_minor"] - ttm["cost_of_revenue_minor"], aid, "margin mismatch")
    _require(sum(r["amount_minor"] - paid[rid] for rid, r in tables["invoices"].items()) == ttm["accounts_receivable_minor"], aid, "receivables mismatch")
    return {name: len(rows) for name, rows in tables.items()}
