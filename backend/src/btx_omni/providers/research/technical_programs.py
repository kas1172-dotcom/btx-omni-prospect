"""Reviewed public, high-level program architecture for bounded Monitor research."""

from __future__ import annotations

import re
from dataclasses import dataclass

from btx_omni.ai.contracts import (
    PublicEvidenceRecord,
    TechnicalBasis,
    TechnicalCandidate,
    TechnicalEvidenceLayer,
)
from btx_omni.providers.research._catalog_support import document


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


@dataclass(frozen=True)
class TechnicalProgramReference:
    id: str
    system_name: str
    aliases: tuple[str, ...]
    sources: tuple[PublicEvidenceRecord, ...]
    components: tuple[TechnicalCandidate, ...]
    validation_questions: tuple[str, ...]


def load_technical_program_references() -> tuple[TechnicalProgramReference, ...]:
    payload = document("technical_program_reference_sources.json")
    result = []
    for program in payload["programs"]:
        source_by_id = {str(source["id"]): source for source in program["sources"]}
        sources = tuple(
            PublicEvidenceRecord(
                evidence_id=str(source["id"]),
                title=str(source["title"]),
                extract=str(source["passage"]),
                source_url=str(source["url"]),
                provenance="|".join(
                    (
                        str(source["publisher"]),
                        str(source.get("publication_date") or "date unavailable"),
                        str(source["extraction_method"]),
                        "complete" if source.get("extraction_complete") else "partial",
                    )
                ),
            )
            for source in program["sources"]
        )
        components = tuple(
            TechnicalCandidate(
                name=str(item["name"]),
                basis=TechnicalBasis.SOURCE_STATED,
                reason="High-level architecture retained from the cited authoritative public source.",
                source_support="Authoritative reviewed public program source",
                evidence_ids=tuple(str(value) for value in item["evidence_ids"]),
                parent_system=str(program["system_name"]),
                parent_component=str(item["parent_component"])
                if item.get("parent_component")
                else None,
                component_category=str(item["category"]),
                evidence_layer=TechnicalEvidenceLayer(str(item["evidence_layer"])),
                confidence_state=str(item["confidence_state"]),
                material_uncertainties=tuple(
                    str(value) for value in item.get("material_uncertainties", ())
                ),
                validation_questions=tuple(
                    str(value) for value in item.get("validation_questions", ())
                ),
                source_publication_dates=tuple(
                    dict.fromkeys(
                        str(source_by_id[value]["publication_date"])
                        for value in item["evidence_ids"]
                        if source_by_id[value].get("publication_date")
                    )
                ),
                research_methods=tuple(
                    dict.fromkeys(
                        str(source_by_id[value]["extraction_method"])
                        for value in item["evidence_ids"]
                    )
                ),
            )
            for item in program["components"]
        )
        result.append(
            TechnicalProgramReference(
                str(program["id"]),
                str(program["system_name"]),
                tuple(str(value) for value in program["aliases"]),
                sources,
                components,
                tuple(str(value) for value in program.get("validation_questions", ())),
            )
        )
    return tuple(result)


def references_for_text(value: str) -> tuple[TechnicalProgramReference, ...]:
    normalized = normalize(value)
    return tuple(
        reference
        for reference in load_technical_program_references()
        if any(normalize(alias) in normalized for alias in reference.aliases)
    )
