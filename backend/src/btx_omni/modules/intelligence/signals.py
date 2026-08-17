"""Deterministic normalization of source-shaped commercial intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState, require_aware


class SignalKind(StrEnum):
    AWARD_CONTRACT = "AWARD_CONTRACT"
    EXPANSION = "EXPANSION"
    PRESS_RELEASE = "PRESS_RELEASE"
    FINANCIAL_REPORT = "FINANCIAL_REPORT"
    INDUSTRY_UPDATE = "INDUSTRY_UPDATE"


class SourceValidationState(StrEnum):
    """Result of reviewing a publisher URL without bypassing publisher controls."""

    BROWSER_VERIFIED = "BROWSER_VERIFIED"
    AUTOMATION_BLOCKED = "AUTOMATION_BLOCKED"
    REPLACED_WITH_EQUIVALENT_OFFICIAL_SOURCE = "REPLACED_WITH_EQUIVALENT_OFFICIAL_SOURCE"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"


@dataclass(frozen=True)
class RawSignal:
    source_id: str
    kind: SignalKind
    title: str
    source_url: str
    occurred_at: datetime
    account_name: str | None
    program_name: str | None
    evidence_state: EvidenceState
    summary: str
    source_validation_state: SourceValidationState = SourceValidationState.NEEDS_RESEARCH


@dataclass(frozen=True)
class IntelligenceSignal:
    id: str
    kind: SignalKind
    title: str
    source_url: str
    account_id: str | None
    program_name: str | None
    evidence_state: EvidenceState
    relevance_explanation: str
    evidence_ids: tuple[str, ...]
    occurred_at: datetime
    provenance: Provenance
    source_validation_state: SourceValidationState = SourceValidationState.NEEDS_RESEARCH

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")


def normalize_signal(raw: RawSignal, *, account_name_to_id: dict[str, str], provenance: Provenance) -> IntelligenceSignal:
    account_id = account_name_to_id.get(raw.account_name or "")
    digest = sha256(f"{raw.source_id}\x1f{raw.source_url}".encode()).hexdigest()[:24]
    evidence_id = f"evidence-signal-{digest}"
    relationship = "a canonical account" if account_id else "no canonical account"
    relevance = f"{raw.kind.value} names {relationship}" + (f" and program {raw.program_name}" if raw.program_name else "") + "; review only the supplied source evidence."
    return IntelligenceSignal(
        f"signal-{digest}", raw.kind, raw.title, raw.source_url, account_id,
        raw.program_name, raw.evidence_state, relevance, (evidence_id,), raw.occurred_at,
        provenance, raw.source_validation_state,
    )
