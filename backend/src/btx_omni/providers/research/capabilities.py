from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.capabilities import Capability
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_capabilities(*, business_unit_ids: set[str]) -> tuple[Capability, ...]:
    payload, result = document("btx_capability_catalog.json"), []
    for row in payload["bu_capabilities"]:
        if row["bu_id"] not in business_unit_ids:
            raise ValueError(f"capability references unknown business unit {row['bu_id']}")
        processes = tuple(item["process"] for item in row["process_families"])
        result.append(Capability(f"cap-{row['bu_id']}", row["bu_id"], (row["bu_id"],), row.get("capacity_notes"), processes, tuple(row.get("certifications", ())), source_provenance({"id": f"cap-{row['bu_id']}"}, classification=Classification.PUBLIC)))
    return tuple(result)
