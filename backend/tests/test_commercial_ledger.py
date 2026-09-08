"""Independent small ledger oracle; not generated from the package's totals."""
from copy import deepcopy

import pytest

from btx_omni.modules.commercial.ledger import (
    KEYS,
    CommercialIntegrityError,
    validate_commercial_account,
)


def small_ledger():
    value = {key: [] for key in KEYS}
    value.update(account_id="test-account", currency="USD", as_of="2026-08-31", public_events=[])
    value["programs"] = [{"program_id": "p"}]
    value["components"] = [{"component_id": "c"}]
    value["rfqs"] = [{"rfq_id": "r"}]
    value["quotes"] = [{"quote_id": "q", "rfq_id": "r", "current_revision_id": "qr"}]
    value["quote_revisions"] = [{"quote_revision_id": "qr", "quote_id": "q", "issued_date": "2026-08-01", "line_ids": ["ql"], "total_minor": 1000, "supersedes_revision_id": None}]
    value["quote_lines"] = [{"quote_line_id": "ql", "quote_revision_id": "qr", "component_id": "c", "quantity": 10, "unit_price_minor": 100, "line_total_minor": 1000}]
    value["orders"] = [{"order_id": "o", "quote_id": "q", "accepted_quote_revision_id": "qr", "agreement_id": None, "ordered_date": "2026-08-02", "line_ids": ["ol"], "total_minor": 1000}]
    value["order_lines"] = [{"order_line_id": "ol", "order_id": "o", "component_id": "c", "quantity": 10, "unit_price_minor": 100, "unit_cost_minor": 60, "line_total_minor": 1000}]
    value["shipments"] = [{"shipment_id": "s", "order_line_id": "ol", "shipped_date": "2026-08-10", "quantity": 6, "value_minor": 600}]
    value["acceptances"] = [{"acceptance_id": "a", "shipment_id": "s", "accepted_date": "2026-08-12", "quantity": 4}]
    value["revenue_events"] = [{"revenue_event_id": "v", "acceptance_id": "a", "order_line_id": "ol", "recognized_date": "2026-08-12", "quantity": 4, "revenue_minor": 400, "cost_minor": 240}]
    value["invoices"] = [{"invoice_id": "i", "revenue_event_id": "v", "invoice_date": "2026-08-12", "amount_minor": 400}]
    value["payments"] = [{"payment_id": "pay", "invoice_id": "i", "paid_date": "2026-08-20", "amount_minor": 150}]
    value["monthly_commercial_history"] = [{"snapshot_id": "m", "period": "2026-08", "opening_backlog_minor": 0, "bookings_minor": 1000, "cancellations_minor": 0, "shipments_minor": 600, "revenue_minor": 400, "cost_of_revenue_minor": 240, "closing_backlog_minor": 400, "business_unit_allocations": [{"business_unit_id": "bu", "bookings_minor": 1000, "shipments_minor": 600, "revenue_minor": 400}]}]
    value["ttm_summary"] = {"bookings_minor": 1000, "shipments_minor": 600, "revenue_minor": 400, "cost_of_revenue_minor": 240, "cancellations_minor": 0, "gross_margin_minor": 160, "accounts_receivable_minor": 250}
    return value


def test_partial_shipment_acceptance_and_payment_have_distinct_balances():
    ledger = small_ledger()
    before = deepcopy(ledger)
    result = validate_commercial_account(ledger)
    assert result["orders"] == 1
    assert ledger == before
    assert ledger["ttm_summary"]["revenue_minor"] != ledger["ttm_summary"]["shipments_minor"]


@pytest.mark.parametrize("collection,field,value", [
    ("quote_lines", "line_total_minor", 1001),
    ("quote_lines", "quantity", True),
    ("quote_lines", "unit_price_minor", 100.0),
    ("quote_lines", "currency", "EUR"),
    ("orders", "account_id", "another-account"),
    ("orders", "ordered_date", "2026-07-31"),
    ("shipments", "quantity", 11),
    ("shipments", "shipped_date", "2026-09-01"),
    ("acceptances", "quantity", 7),
    ("acceptances", "accepted_date", "2026-08-09"),
    ("revenue_events", "revenue_minor", 600),
    ("revenue_events", "acceptance_id", "missing"),
    ("payments", "amount_minor", 401),
    ("monthly_commercial_history", "revenue_minor", 401),
])
def test_corrupt_record_is_rejected(collection, field, value):
    ledger = small_ledger()
    ledger[collection][0][field] = value
    with pytest.raises(CommercialIntegrityError):
        validate_commercial_account(ledger)


def test_duplicate_identity_and_public_events_are_rejected():
    ledger = small_ledger()
    ledger["orders"].append(deepcopy(ledger["orders"][0]))
    with pytest.raises(CommercialIntegrityError, match="duplicate record"):
        validate_commercial_account(ledger)
    ledger = small_ledger()
    ledger["public_events"] = [{"id": "fabricated-award"}]
    with pytest.raises(CommercialIntegrityError, match="Monitor"):
        validate_commercial_account(ledger)


def test_duplicate_recognition_with_new_id_is_rejected():
    ledger = small_ledger()
    duplicate = {**ledger["revenue_events"][0], "revenue_event_id": "v2"}
    ledger["revenue_events"].append(duplicate)
    with pytest.raises(CommercialIntegrityError, match="duplicate recognition"):
        validate_commercial_account(ledger)
