"""Validate method-specific lineage without changing scoring policy."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from btx_omni.domain.common import DataMode

if TYPE_CHECKING:
    from btx_omni.modules.classification.records import FactorClassification


def validate_classification(record: FactorClassification) -> None:
    if not all((record.classification_id, record.subject_kind, record.subject_id,
                record.family, record.factor_path, record.scorer_rule_version)):
        raise ValueError("Classification identity, scope, and scorer version are required")
    if record.method not in {"DETERMINISTIC", "SYNTHETIC_AUTHORED"}:
        raise ValueError("Unknown classification method")
    if record.state not in {"CURRENT", "MISSING", "STALE", "CONFLICTING"}:
        raise ValueError("Unknown classification state")
    if record.value_kind not in {"BIN", "RAW_INPUT", "REVIEWED_CLAIMS"}:
        raise ValueError("Unknown classification value kind")
    populated = int(record.bin_value is not None) + int(record.raw_input is not None)
    if populated > 1 or (record.state == "CURRENT" and populated != 1) or (record.state != "CURRENT" and populated):
        raise ValueError("A current classification requires exactly one value; missing/stale/conflicting have none")
    if record.bin_value is not None and (record.value_kind != "BIN" or not record.bin_value):
        raise ValueError("Bin classifications require a nonempty bin literal")
    if record.raw_input is not None and (record.value_kind == "BIN" or not record.raw_input):
        raise ValueError("Raw classifications require nonempty input")
    for field in ("classified_at", "observed_as_of", "authored_at"):
        value = getattr(record, field)
        if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
            raise ValueError(f"{field} must be timezone-aware")
    if record.method == "DETERMINISTIC":
        if not record.classifier_rule_version or (record.state == "CURRENT" and not record.evidence_ids):
            raise ValueError("Deterministic classifications require a rule version and current evidence")
        if record.authored_by or record.authored_at:
            raise ValueError("Deterministic classifications cannot claim fixture authorship")
    else:
        if not record.authored_by or not record.authored_at or not record.note or len(record.note.strip()) < 12:
            raise ValueError("Authored classifications require author, time, and substantive note")
        if record.classifier_rule_version:
            raise ValueError("Authored classifications have no deterministic rule version")
        if record.provenance.data_mode is not DataMode.SAMPLE or not record.provenance.synthetic:
            raise ValueError("Synthetic authored classification must retain SAMPLE/synthetic provenance")
        if getattr(record.provenance, "truth_class", None) != "POC_SCENARIO":
            raise ValueError("Synthetic authored classification requires POC_SCENARIO truth class")
    if record.provenance.data_mode is DataMode.SAMPLE and not record.provenance.synthetic:
        raise ValueError("SAMPLE classification outputs must remain synthetic")


def classification_payload(record: FactorClassification) -> dict:
    """JSON-shaped sidecar; legacy scorer fields remain untouched."""
    result = asdict(record)
    for field in ("authored_at", "observed_as_of", "classified_at"):
        if result[field] is not None:
            result[field] = result[field].isoformat()
    for field in ("observed_at", "recorded_at"):
        result["provenance"][field] = result["provenance"][field].isoformat()
    result["provenance"]["sensitivity_tags"] = sorted(result["provenance"]["sensitivity_tags"])
    if getattr(record.provenance, "truth_class", None):
        result["provenance"]["truth_class"] = record.provenance.truth_class
    return result


def deterministic_bin(*, opportunity_id: str, path: str, bin_value: str | None,
                      evidence_ids: tuple[str, ...], missing_fields: tuple[str, ...], as_of: str,
                      rule_version: str) -> FactorClassification:
    """Build a SAMPLE-derived leaf; missing facts are not low-valued bins."""
    from datetime import UTC

    from btx_omni.core.classification import Classification
    from btx_omni.domain.common import EvidenceState
    from btx_omni.modules.classification.records import ClassificationProvenance, FactorClassification
    from btx_omni.modules.scoring.families import VERSION as SCORER_VERSION

    observed = datetime.fromisoformat(as_of).replace(tzinfo=UTC)
    state = "CURRENT" if bin_value is not None else "MISSING"
    identity = f"{opportunity_id}:{path}:{rule_version}"
    provenance = ClassificationProvenance("sample-classifier", identity, None, observed, observed,
        Classification.INTERNAL_COMMERCIAL,
        EvidenceState.CONFIRMED if bin_value is not None else EvidenceState.MISSING,
        DataMode.SAMPLE, True, missing_fields=missing_fields)
    return FactorClassification(identity, "opportunity", opportunity_id, "opportunity_priority", path,
        "BIN", bin_value, None, state, "DETERMINISTIC", rule_version, SCORER_VERSION,
        evidence_ids, (), None, None, None, observed, observed, provenance)


def deterministic_raw(*, opportunity_id: str, factor: str, raw_input: dict | None,
                      evidence_ids: tuple[str, ...], missing_fields: tuple[str, ...], as_of: str,
                      rule_version: str) -> FactorClassification:
    """Build a delivery input without turning missing capacity into a low score."""
    from datetime import UTC

    from btx_omni.core.classification import Classification
    from btx_omni.domain.common import EvidenceState
    from btx_omni.modules.classification.records import ClassificationProvenance, FactorClassification
    from btx_omni.modules.scoring.families import VERSION as SCORER_VERSION

    observed = datetime.fromisoformat(as_of).replace(tzinfo=UTC)
    state = "CURRENT" if raw_input is not None else "MISSING"
    identity = f"{opportunity_id}:delivery_feasibility.{factor}:{rule_version}"
    provenance = ClassificationProvenance("sample-classifier", identity, None, observed, observed,
        Classification.INTERNAL_COMMERCIAL,
        EvidenceState.CONFIRMED if raw_input is not None else EvidenceState.MISSING,
        DataMode.SAMPLE, True, missing_fields=missing_fields)
    return FactorClassification(identity, "opportunity", opportunity_id, "delivery_feasibility", factor,
        "RAW_INPUT", None, raw_input, state, "DETERMINISTIC", rule_version, SCORER_VERSION,
        evidence_ids, (), None, None, None, observed, observed, provenance)
