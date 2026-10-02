"""Immutable evidence-linked classification, distinct from scorer results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from btx_omni.core.provenance import Provenance


@dataclass(frozen=True)
class ClassificationProvenance(Provenance):
    """Classification-only truth label; core source provenance stays unchanged."""

    truth_class: str = "POC_SCENARIO"


@dataclass(frozen=True)
class FactorClassification:
    classification_id: str
    subject_kind: str
    subject_id: str
    family: str
    factor_path: str
    value_kind: Literal["BIN", "RAW_INPUT", "REVIEWED_CLAIMS"]
    bin_value: str | None
    raw_input: Mapping[str, object] | None
    state: Literal["CURRENT", "MISSING", "STALE", "CONFLICTING"]
    method: Literal["DETERMINISTIC", "SYNTHETIC_AUTHORED"]
    classifier_rule_version: str | None
    scorer_rule_version: str
    evidence_ids: tuple[str, ...]
    source_revision_ids: tuple[str, ...]
    authored_by: str | None
    authored_at: datetime | None
    note: str | None
    observed_as_of: datetime | None
    classified_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        from btx_omni.modules.classification.contract import validate_classification

        validate_classification(self)
