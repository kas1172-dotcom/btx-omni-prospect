from __future__ import annotations

from dataclasses import dataclass

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState


@dataclass(frozen=True)
class Program:
    id: str
    account_id: str | None
    name: str
    system: str | None
    evidence_state: EvidenceState
    provenance: Provenance


@dataclass(frozen=True)
class ComponentClass:
    id: str
    program_id: str
    name: str
    evidence_state: EvidenceState
    provenance: Provenance
