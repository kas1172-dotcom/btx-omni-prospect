"""Governed account relationship edges; traversal remains intentionally deferred."""
from __future__ import annotations

from dataclasses import dataclass

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState


@dataclass(frozen=True)
class AccountRelationshipEdge:
    id: str
    from_account_id: str
    to_account_id: str
    edge_type: str
    direction: str
    strength: str
    evidence_state: EvidenceState
    source_ids: tuple[str, ...]
    narrative: str | None
    program_id: str | None
    provenance: Provenance
