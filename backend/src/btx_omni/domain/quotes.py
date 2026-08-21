from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from btx_omni.core.provenance import Provenance


class QuoteStatus(StrEnum):
    OPEN = "OPEN"
    WON = "WON"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class PaperlessAccount:
    """Paperless account identity, distinct from its quotes and canonical account."""

    id: str
    canonical_account_id: str
    name: str
    provenance: Provenance


@dataclass(frozen=True)
class CommercialQuote:
    id: str
    account_id: str
    business_unit: str
    status: QuoteStatus
    quoted_at: date
    value_minor: int | None
    currency: str
    contact_id: str | None
    facility_id: str | None
    part_family: str | None
    provenance: Provenance
    quote_to_book_evidence_ids: tuple[str, ...] = ()
    program_id: str | None = None
    component_class_ids: tuple[str, ...] = ()
    paperless_account_id: str | None = None
    paperless_contact_id: str | None = None
    line_items: tuple[CommercialQuoteLineItem, ...] = ()


@dataclass(frozen=True)
class CommercialQuoteLineItem:
    id: str
    part_number: str
    component_class_id: str
    quantity: int
    unit_price_minor: int
    lead_time_days: int | None
    provenance: Provenance
