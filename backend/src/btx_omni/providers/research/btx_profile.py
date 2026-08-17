from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.btx import BtxBusinessUnit
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_btx_business_units() -> tuple[BtxBusinessUnit, ...]:
    payload = document("btx_company_profile.json")
    source_ids = set(payload["sources"])
    units = []
    for row in payload["business_units"]:
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"business unit {row['id']} has unknown source")
        units.append(BtxBusinessUnit(row["id"], row["display_name"], row.get("website"), tuple(row.get("processes", ())), tuple(row.get("certifications", ())), source_provenance(row, classification=Classification.PUBLIC)))
    return tuple(units)
