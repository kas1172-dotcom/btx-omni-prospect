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
    expected_production_horizon_years: int | None = None
    commitment_strength: str | None = None
    maturity_evidence: str | None = None


@dataclass(frozen=True)
class ComponentClass:
    id: str
    program_id: str | None
    name: str
    evidence_state: EvidenceState
    provenance: Provenance
    industry: str | None = None
    business_unit_ids: tuple[str, ...] = ()
    typical_materials: tuple[str, ...] = ()
    typical_processes: tuple[str, ...] = ()
    typical_tolerance: str | None = None
    typical_size_bracket: str | None = None
