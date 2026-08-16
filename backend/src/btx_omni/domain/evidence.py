from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState, require_aware


@dataclass(frozen=True)
class SourceIdentity:
    """A source-system identity mapped to one canonical account."""

    source_system: str
    source_key: str
    canonical_account_id: str
    provenance: Provenance


@dataclass(frozen=True)
class Evidence:
    id: str
    subject_id: str
    summary: str
    state: EvidenceState
    provenance: Provenance
    occurred_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
        if self.state is EvidenceState.MISSING and self.summary.strip():
            raise ValueError("missing evidence cannot claim a value")
