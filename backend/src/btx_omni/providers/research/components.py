from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.common import EvidenceState
from btx_omni.domain.markets import normalize_source_market
from btx_omni.domain.programs import ComponentClass
from btx_omni.providers.research._catalog_support import document, source_provenance

# Source names that intentionally map to differently named ComponentClass fields.
FIELD_ALIASES = {"display_name": "name", "btx_bu_fit": "business_unit_ids", "industry_primary": "industry"}
DROPPED_FIELDS = {
    "source_ids": "Validated against catalog sources; individual source IDs are not model fields.",
    "industries_all": "Deferred; revisit when a multi-industry component consumer exists.",
    "case_study_evidence": "Deferred; revisit when a consumer exists.",
    "regulatory_note": "Deferred; revisit when a consumer exists.",
    "workbook_sha256": "Source-provenance bookkeeping, not a component attribute.",
    "sheet": "Source-provenance bookkeeping, not a component attribute.",
    "row_number": "Source-provenance bookkeeping, not a component attribute.",
}


def load_component_classes(*, business_unit_ids: set[str]) -> tuple[ComponentClass, ...]:
    payload = document("btx_component_taxonomy.json")
    source_ids, result = set(payload["sources"]), []
    for row in payload["component_classes"]:
        if not set(row["btx_bu_fit"]) <= business_unit_ids:
            raise ValueError(f"component {row['id']} has unknown business unit")
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"component {row['id']} has unknown source")
        industry = normalize_source_market(row["industry_primary"]) if row.get("industry_primary") else None
        result.append(ComponentClass(
            row["id"], None, row["display_name"], EvidenceState.CONFIRMED,
            source_provenance(row, classification=Classification.PUBLIC), industry, tuple(row["btx_bu_fit"]),
            typical_materials=tuple(row.get("typical_materials") or ()),
            typical_processes=tuple(row.get("typical_processes") or ()),
            typical_tolerance=row.get("typical_tolerance"),
            typical_size_bracket=row.get("typical_size_bracket"),
        ))
    return tuple(result)
