from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.capabilities import Capability, CapabilityProcessFamily
from btx_omni.providers.research._catalog_support import document, source_provenance

FIELD_ALIASES = {"bu_id": "business_units", "capacity_notes": "description"}
DROPPED_FIELDS = {
    "workbook_sha256": "Source-provenance bookkeeping, not a capability attribute.",
    "sheet": "Source-provenance bookkeeping, not a capability attribute.",
    "row_number": "Source-provenance bookkeeping, not a capability attribute.",
}


def load_capabilities(*, business_unit_ids: set[str]) -> tuple[Capability, ...]:
    payload, result = document("btx_capability_catalog.json"), []
    for row in payload["bu_capabilities"]:
        if row["bu_id"] not in business_unit_ids:
            raise ValueError(f"capability references unknown business unit {row['bu_id']}")
        process_families = tuple(
            CapabilityProcessFamily(
                process=item["process"],
                envelope_directional=item.get("envelope_directional"),
                materials_supported=tuple(item.get("materials_supported") or ()),
                tolerance_capability=item.get("tolerance_capability"),
                certifications_applicable=tuple(item.get("certifications_applicable") or ()),
                specialty_note=item.get("specialty_note"),
            )
            for item in row.get("process_families") or ()
        )
        processes = tuple(item.process for item in process_families)
        result.append(Capability(
            f"cap-{row['bu_id']}", row["bu_id"], (row["bu_id"],), row.get("capacity_notes"),
            processes, tuple(row.get("certifications") or ()),
            source_provenance({"id": f"cap-{row['bu_id']}"}, classification=Classification.PUBLIC),
            volume_profile=tuple(row.get("volume_profile") or ()),
            process_families=process_families,
            industries_served=tuple(row.get("industries_served") or ()),
            materials_specialty=row.get("materials_specialty"),
            unique_capabilities=tuple(row.get("unique_capabilities") or ()),
            geography_advantage=row.get("geography_advantage"),
        ))
    return tuple(result)
