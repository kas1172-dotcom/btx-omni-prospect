"""Provenance carried by every governed source-shaped fact."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btx_omni.core.classification import Classification, SensitivityTag
from btx_omni.domain.common import DataMode, EvidenceState, require_aware


@dataclass(frozen=True)
class Provenance:
    source_system: str
    source_record_id: str
    source_url: str | None
    observed_at: datetime
    recorded_at: datetime
    classification: Classification
    evidence_state: EvidenceState
    data_mode: DataMode
    synthetic: bool
    sensitivity_tags: frozenset[SensitivityTag] = frozenset()
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "observed_at")
        require_aware(self.recorded_at, "recorded_at")
        if self.data_mode in {DataMode.CONNECTED, DataMode.IMPORTED} and self.synthetic:
            raise ValueError("connected and imported facts cannot be synthetic")
