"""Small strict primitives shared by supplied BTX catalog loaders."""
from __future__ import annotations

import json
from btx_omni.core.clock import as_of_datetime
from pathlib import Path

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState

RESEARCH_DIR = Path(__file__).resolve().parents[5] / "docs" / "research"


def document(filename: str) -> dict[str, object]:
    payload = json.loads((RESEARCH_DIR / filename).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError(f"{filename} has unsupported schema_version")
    return payload


def source_provenance(
    record: dict[str, object], *, classification: Classification, default_mode: DataMode = DataMode.CONNECTED,
    default_synthetic: bool = False,
) -> Provenance:
    payload = record.get("provenance")
    if isinstance(payload, dict):
        mode, synthetic = DataMode(payload.get("data_mode", default_mode)), bool(payload.get("synthetic", default_synthetic))
        source_system, source_id = str(payload.get("source_system", "btx-research")), str(payload.get("source_record_id", record.get("id", record.get("edge_id", "unknown"))))
        evidence = EvidenceState(payload.get("evidence_state", record.get("evidence_state", "CONFIRMED")))
    else:
        mode, synthetic, source_system = default_mode, default_synthetic, "btx-research"
        source_id = str(record.get("id", record.get("edge_id", "unknown")))
        evidence = EvidenceState(record.get("evidence_state", "CONFIRMED"))
    now = as_of_datetime()
    source_url = payload.get("source_url") if isinstance(payload, dict) else record.get("source_url")
    return Provenance(source_system, source_id, str(source_url) if source_url is not None else None, now, now, classification, evidence, mode, synthetic)


def require_ids(record: dict[str, object], key: str, valid: set[str], label: str) -> None:
    for value in record.get(key, []):
        if value not in valid:
            raise ValueError(f"{label} references unknown {value!r}")
