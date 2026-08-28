from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.common import EvidenceState
from btx_omni.domain.markets import normalize_source_market
from btx_omni.domain.programs import ComponentClass
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_component_classes(*, business_unit_ids: set[str]) -> tuple[ComponentClass, ...]:
    payload = document("btx_component_taxonomy.json")
    source_ids, result = set(payload["sources"]), []
    for row in payload["component_classes"]:
        if not set(row["btx_bu_fit"]) <= business_unit_ids:
            raise ValueError(f"component {row['id']} has unknown business unit")
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"component {row['id']} has unknown source")
        industry = normalize_source_market(row["industry_primary"]) if row.get("industry_primary") else None
        result.append(ComponentClass(row["id"], None, row["display_name"], EvidenceState.CONFIRMED, source_provenance(row, classification=Classification.PUBLIC), industry, tuple(row["btx_bu_fit"])))
    return tuple(result)
