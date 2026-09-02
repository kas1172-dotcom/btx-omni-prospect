"""Provider-neutral, read-only commercial context for one canonical Customer."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

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
        return CommercialAccountSnapshot(canonical_account_id, contexts, paperless_accounts, quotes, orders, crm, {
            "commercial": self._state("commercial", bool(contexts)),
            "paperless": self._state("paperless", bool(paperless_accounts or quotes)),
            "crm": self._state("crm", bool(companies)),
            "orders": self._state("orders", bool(orders)),
        })
