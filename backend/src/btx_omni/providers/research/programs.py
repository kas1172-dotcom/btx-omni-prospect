from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.common import EvidenceState
from btx_omni.domain.markets import normalize_source_market
from btx_omni.domain.programs import Program
from btx_omni.providers.research._catalog_support import document, source_provenance

FIELD_ALIASES = {"prime_account_id": "account_id", "industry": "system"}
DROPPED_FIELDS = {
    "source_ids": "Validated against catalog sources; individual source IDs are not model fields.",
    "partners": "External partner names deliberately excluded from canonical account FK resolution.",
    "component_context": "Deferred; revisit when a consumer exists.",
    "program_of_record": "Deferred; revisit when a consumer exists.",
    "note_from_figma": "Authoring artifact, not a program attribute.",
    "referenced_by_btx": "Catalog bookkeeping, not a verified BTX program relationship.",
    "referenced_by_btx_source": "Catalog bookkeeping, not a verified BTX program relationship.",
    "workbook_sha256": "Source-provenance bookkeeping, not a program attribute.",
    "sheet": "Source-provenance bookkeeping, not a program attribute.",
    "row_number": "Source-provenance bookkeeping, not a program attribute.",
}


def load_programs(*, account_ids: set[str]) -> tuple[Program, ...]:
    payload = document("btx_program_catalog.json")
    source_ids, result = set(payload["sources"]), []
    for row in payload["programs"]:
        # Catalog partners may name external public organizations; only canonical
        # account IDs are foreign keys in this bounded runtime.
        prime_account_id = row.get("prime_account_id") if row.get("prime_account_id") in account_ids else None
        if not set(row["source_ids"]) <= source_ids:
            raise ValueError(f"program {row['id']} has unknown source")
        industry = normalize_source_market(row["industry"]) if row.get("industry") else None
        result.append(Program(
            row["id"], prime_account_id, row["name"], industry, EvidenceState.CONFIRMED,
            source_provenance(row, classification=Classification.PUBLIC),
            expected_production_horizon_years=row.get("expected_production_horizon_years"),
            commitment_strength=row.get("commitment_strength"),
            maturity_evidence=row.get("maturity_evidence"),
        ))
    # Paperless explicitly uses this unassigned-work bucket. It is a catalog
    # sentinel rather than an asserted customer program, and remains sourced.
    result.append(Program("general-account-work", None, "General account work", None, EvidenceState.MISSING, source_provenance({"id": "general-account-work", "evidence_state": "MISSING"}, classification=Classification.INTERNAL_COMMERCIAL)))
    return tuple(result)
