"""SAMPLE classification sidecars with unchanged legacy scorer-facing fields."""

from __future__ import annotations

from datetime import UTC, datetime

from btx_omni.core.classification import Classification
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.modules.classification.contract import classification_payload
from btx_omni.modules.classification.records import ClassificationProvenance, FactorClassification
from btx_omni.modules.scoring.families import VERSION as SCORER_VERSION
from btx_omni.providers.sample.enhancement import synthetic_record

AUTHOR = "sample_fixture_author"
AUTHORED_AT = datetime(2026, 9, 20, tzinfo=UTC)


def _clock(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=UTC)


def sample_provenance(source_id: str, day: str, *, missing_fields: tuple[str, ...] = ()) -> ClassificationProvenance:
    return ClassificationProvenance("sample-classification", source_id, None, _clock(day), AUTHORED_AT,
                      Classification.INTERNAL_COMMERCIAL, EvidenceState.MISSING if missing_fields else EvidenceState.CONFIRMED,
                      DataMode.SAMPLE, True, missing_fields=missing_fields)


def authored_bin_row(*, opportunity_id: str, path: str, bin_value: str, as_of: str,
                     evidence_ids: tuple[str, ...], note: str) -> dict:
    record = FactorClassification(
        f"{opportunity_id}:{path}:authored", "opportunity", opportunity_id, "opportunity_priority", path,
        "BIN", bin_value, None, "CURRENT", "SYNTHETIC_AUTHORED", None, SCORER_VERSION,
        evidence_ids, (), AUTHOR, AUTHORED_AT, note, _clock(as_of), _clock(as_of),
        sample_provenance(f"{opportunity_id}:{path}:authored", as_of),
    )
    return synthetic_record(opportunity_id=opportunity_id, path=path, bin=bin_value,
                            reviewed_as_of=as_of, evidence_ids=list(evidence_ids), narrative=note,
                            classification=classification_payload(record))


def authored_input_row(*, opportunity_id: str, family: str, factor: str, raw: dict,
                       facility_id: str, as_of: str, note: str) -> dict:
    record = FactorClassification(
        f"{opportunity_id}:{family}.{factor}:authored", "opportunity", opportunity_id, family, factor,
        "RAW_INPUT", None, raw, "CURRENT", "SYNTHETIC_AUTHORED", None, SCORER_VERSION,
        (opportunity_id,), (), AUTHOR, AUTHORED_AT, note, _clock(as_of), _clock(as_of),
        sample_provenance(f"{opportunity_id}:{family}.{factor}:authored", as_of),
    )
    return synthetic_record(**raw, opportunity_id=opportunity_id, facility_id=facility_id,
                            reviewed_as_of=as_of, evidence_ids=[opportunity_id], narrative=note,
                            classification=classification_payload(record))


def refresh_authored_bins(account: dict) -> None:
    """Variants mutate authored bins; keep their sidecars scoped to final values."""
    for opportunity in account["opportunities"]:
        for row in opportunity.get("score_observations", []):
            if not row.get("classification") or row["classification"]["method"] != "SYNTHETIC_AUTHORED":
                continue
            oid, path = opportunity["opportunity_id"], row["path"]
            if (row["classification"]["subject_id"], row["classification"]["bin_value"]) != (oid, row["bin"]):
                refreshed = authored_bin_row(opportunity_id=oid, path=path, bin_value=row["bin"],
                    as_of=row["reviewed_as_of"], evidence_ids=tuple(row["evidence_ids"]),
                    note="Authored SAMPLE variant assumption; not a verified customer fact.")
                row["classification"] = refreshed["classification"]
