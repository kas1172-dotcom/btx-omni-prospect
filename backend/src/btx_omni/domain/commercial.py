from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from btx_omni.core.provenance import Provenance


@dataclass(frozen=True)
class MonthlyCommercialHistory:
    month: date
    revenue_minor: int | None
    bookings_minor: int | None
    provenance: Provenance


@dataclass(frozen=True)
class CommercialContext:
    account_id: str
    business_unit: str
    currency: str
    ttm_revenue_minor: int | None
    ttm_bookings_minor: int | None
    customer_segment: str | None
    end_market: str | None
    platform_program: str | None
    part_number: str | None
    last_booking_date: date | None
    last_order_date: date | None
    monthly_history: tuple[MonthlyCommercialHistory, ...]
    provenance: Provenance
    last_crm_activity_date: date | None = None
    intelligence_evidence_ids: tuple[str, ...] = ()
    jamie_validation_required: tuple[str, ...] = ()
