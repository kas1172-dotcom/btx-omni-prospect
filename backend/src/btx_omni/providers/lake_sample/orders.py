from __future__ import annotations

from datetime import date

from btx_omni.core.classification import Classification
from btx_omni.domain.orders import Order
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_orders(*, account_ids: set[str], business_unit_ids: set[str], program_ids: set[str], component_ids: set[str], quote_ids: set[str]) -> tuple[Order, ...]:
    payload, result = document("btx_sample_orders.json"), []
    for row in payload["orders"]:
        if row["research_account_id"] not in account_ids or row["business_unit_id"] not in business_unit_ids or row["program_id"] not in program_ids or row["component_class_id"] not in component_ids:
            raise ValueError(f"order {row['order_id']} has an unknown foreign key")
        if row.get("quote_id") and row["quote_id"] not in quote_ids:
            raise ValueError(f"order {row['order_id']} references unknown quote")
        result.append(Order(row["order_id"], row.get("quote_id"), row["research_account_id"], row["business_unit_id"], row["part_number"], row["component_class_id"], row["program_id"], row.get("ship_to_city"), row.get("ship_to_state"), date.fromisoformat(row["promised_date"]) if row.get("promised_date") else None, date.fromisoformat(row["actual_ship_date"]) if row.get("actual_ship_date") else None, row["status"], row["quantity"], row["line_amount_cents"], source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL)))
    return tuple(result)
