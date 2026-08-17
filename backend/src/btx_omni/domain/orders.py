"""Order facts supplied by a lake-shaped commercial provider."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from btx_omni.core.provenance import Provenance


@dataclass(frozen=True)
class Order:
    id: str
    quote_id: str | None
    account_id: str
    business_unit_id: str
    part_number: str
    component_class_id: str
    program_id: str
    ship_to_city: str | None
    ship_to_region: str | None
    promised_date: date | None
    actual_ship_date: date | None
    status: str
    quantity: int
    amount_minor: int
    provenance: Provenance
