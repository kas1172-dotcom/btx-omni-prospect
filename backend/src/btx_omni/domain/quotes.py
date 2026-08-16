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
