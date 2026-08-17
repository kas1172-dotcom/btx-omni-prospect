from __future__ import annotations

from collections import defaultdict
from datetime import date

from btx_omni.core.classification import Classification
from btx_omni.domain.commercial import CommercialContext, MonthlyCommercialHistory
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_commercial_contexts(*, account_ids: set[str], business_unit_ids: set[str]) -> tuple[CommercialContext, ...]:
    payload = document("btx_sample_commercial_context.json")
    history: dict[tuple[str, str], list[MonthlyCommercialHistory]] = defaultdict(list)
    for row in payload["monthly_rows"]:
        if row["research_account_id"] not in account_ids or row["business_unit_id"] not in business_unit_ids:
            raise ValueError("commercial monthly row has unknown account or business unit")
        history[(row["research_account_id"], row["business_unit_id"])].append(MonthlyCommercialHistory(date.fromisoformat(row["month"]), row.get("revenue_cents"), row.get("bookings_cents"), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL)))
    contexts = []
    for row in payload["ttm_aggregates_derived"]:
        key = (row["research_account_id"], row["business_unit_id"])
        if key not in history:
            raise ValueError(f"commercial aggregate {key!r} lacks monthly source rows")
        contexts.append(CommercialContext(key[0], key[1], row["currency"], row.get("ttm_revenue_cents"), row.get("ttm_bookings_cents"), row.get("customer_segment"), row.get("end_market"), None, None, date.fromisoformat(row["last_booking_date"]) if row.get("last_booking_date") else None, date.fromisoformat(row["last_order_date"]) if row.get("last_order_date") else None, tuple(sorted(history[key], key=lambda item: item.month)), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL), jamie_validation_required=("SAMPLE commercial context; confirm against connected lake before action.",)))
    return tuple(contexts)
