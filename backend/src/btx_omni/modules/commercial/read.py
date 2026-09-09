"""Provider-neutral, read-only commercial context for one canonical Customer."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from btx_omni.providers.sample.environment import SampleEnvironment


@dataclass(frozen=True)
class CommercialAccountSnapshot:
    canonical_account_id: str
    commercial_context: tuple[object, ...]
    paperless_accounts: tuple[object, ...]
    quotes: tuple[object, ...]
    orders: tuple[object, ...]
    crm: dict[str, tuple[object, ...]]
    source_states: dict[str, dict[str, str]]
    ledger_summary: dict = field(default_factory=dict)


class CommercialReadService:
    """The runtime-owned boundary between seller projections and providers.

    SAMPLE data remains explicitly simulated. CONNECTED selection is fail-closed
    at the runtime before this service can be reached.
    """

    def __init__(self, sample: SampleEnvironment, *, source_states: Mapping[str, tuple[str, str]] | None = None) -> None:
        self.sample = sample
        self._source_states = dict(source_states or {})

    def _state(self, domain: str, has_data: bool) -> dict[str, str]:
        data_mode, source_state = self._source_states.get(
            domain, ("SAMPLE", "AVAILABLE" if has_data else "NO_LINKED_DATA")
        )
        return {"data_mode": data_mode, "source_state": source_state}

    def account_snapshot(self, canonical_account_id: str) -> CommercialAccountSnapshot:
        contexts = tuple(item for item in self.sample.commercial_contexts if item.account_id == canonical_account_id)
        paperless_accounts = tuple(item for item in self.sample.paperless_accounts if item.canonical_account_id == canonical_account_id)
        quotes = tuple(item for item in self.sample.quotes if item.account_id == canonical_account_id)
        orders = tuple(item for item in self.sample.orders if item.account_id == canonical_account_id)
        companies = tuple(item for item in self.sample.crm_companies if item.account_id == canonical_account_id)
        company_ids = {item.id for item in companies}
        crm = {"companies": companies, "contacts": tuple(item for item in self.sample.crm_contacts if item.company_id in company_ids), "deals": tuple(item for item in self.sample.crm_deals if item.company_id in company_ids), "activities": tuple(item for item in self.sample.crm_activities if item.company_id in company_ids)}
        ledger = self.sample.commercial_ledgers.get(canonical_account_id)
        summary = {} if ledger is None else {
            "as_of": ledger["as_of"], "currency": ledger["currency"],
            "ttm": ledger["ttm_summary"], "revision": self.sample.commercial_revision,
            "monthly_history": ledger["monthly_commercial_history"],
            "record_counts": {key: len(value) for key, value in ledger.items() if isinstance(value, list)},
        }
        return CommercialAccountSnapshot(canonical_account_id, contexts, paperless_accounts, quotes, orders, crm, {
            "commercial": self._state("commercial", bool(contexts)),
            "paperless": self._state("paperless", bool(paperless_accounts or quotes)),
            "crm": self._state("crm", bool(companies)),
            "orders": self._state("orders", bool(orders)),
        }, summary)

    def quote_comparison(self, account_id: str, quote_id: str) -> dict:
        ledger = self.sample.commercial_ledgers.get(account_id)
        if ledger is None:
            raise ValueError("No canonical commercial history in this account scope.")
        quote = next((q for q in ledger["quotes"] if q["quote_id"] == quote_id), None)
        if quote is None:
            raise ValueError("Quote does not belong to the resolved account.")
        revisions = sorted((r for r in ledger["quote_revisions"] if r["quote_id"] == quote_id), key=lambda r: (r["revision_number"], r["quote_revision_id"]))
        result = []
        previous = None
        for revision in revisions:
            lines = [line for line in ledger["quote_lines"] if line["quote_revision_id"] == revision["quote_revision_id"]]
            result.append({**revision, "lines": lines, "total_delta_minor": revision["total_minor"] - previous["total_minor"] if previous else None})
            previous = revision
        orders = [order for order in ledger["orders"] if order["quote_id"] == quote_id and order["ordered_date"] <= ledger["as_of"]]
        order_ids = {order["order_id"] for order in orders}
        line_ids = {line["order_line_id"] for line in ledger["order_lines"] if line["order_id"] in order_ids}
        revenue = [row for row in ledger["revenue_events"] if row["order_line_id"] in line_ids and row["recognized_date"] <= ledger["as_of"]]
        return {"account_id": account_id, "as_of": ledger["as_of"], "revision": self.sample.commercial_revision,
                "currency": ledger["currency"], "quote": quote, "revisions": result,
                "linked_recorded_order_ids": sorted(order_ids), "linked_recorded_order_value_minor": sum(order["total_minor"] for order in orders),
                "linked_recorded_revenue_minor": sum(row["revenue_minor"] for row in revenue),
                "revenue_event_ids": [row["revenue_event_id"] for row in revenue],
                "meaning": "Revisions are alternatives, not additive bookings. Only an explicitly accepted revision supports accepted work."}
