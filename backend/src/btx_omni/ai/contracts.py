from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProviderStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTH_FAILED = "AUTH_FAILED"
    TIMEOUT = "TIMEOUT"
    QUOTA = "QUOTA"
    UNAVAILABLE = "UNAVAILABLE"


class ReadIntent(StrEnum):
    """Only existing governed read routes may be selected by a language provider."""

    ACCOUNT_OVERVIEW = "ACCOUNT_OVERVIEW"
    ACCOUNT_INTELLIGENCE = "ACCOUNT_INTELLIGENCE"
    ACCOUNT_SIGNIFICANCE = "ACCOUNT_SIGNIFICANCE"
    ACCOUNT_NEXT_ACTION = "ACCOUNT_NEXT_ACTION"
    ACCOUNT_ACTIONS = "ACCOUNT_ACTIONS"
    ACCOUNT_QUOTES = "ACCOUNT_QUOTES"
    SCREEN_SUMMARY = "SCREEN_SUMMARY"
    GENERAL_OVERVIEW = "GENERAL_OVERVIEW"


class TechnicalBasis(StrEnum):
    """Whether a technical item is stated by evidence or an AI hypothesis."""

    SOURCE_STATED = "SOURCE_STATED"
    MODEL_INFERRED = "MODEL_INFERRED"


class LanguageProviderError(RuntimeError):
    """Safe provider failure classification; messages never cross the API boundary."""

    def __init__(self, status: ProviderStatus) -> None:
        super().__init__(status.value)
        self.status = status


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str


@dataclass(frozen=True)
class IntentInterpretationRequest:
    question: str
    recent_turns: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True)
class IntentInterpretation:
    intent: ReadIntent
    entity_text: str | None = None


@dataclass(frozen=True)
class GroundedSynthesisRequest:
    question: str
    governed_answer: str
    evidence_ids: tuple[str, ...]
    missingness: tuple[str, ...]
    recent_turns: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True)
class PublicEvidenceRecord:
    """Bounded public evidence supplied as content, never as instructions."""

    evidence_id: str
    title: str
    extract: str
    source_url: str | None = None
    provenance: str | None = None


@dataclass(frozen=True)
class TechnicalCandidate:
    name: str
    basis: TechnicalBasis
    reason: str
    source_support: str
    evidence_ids: tuple[str, ...] = ()
    parent_system: str | None = None
    parent_product: str | None = None
    manufacturing_family: str | None = None

    def __post_init__(self) -> None:
        for value in (self.name, self.reason, self.source_support):
            if not value.strip() or len(value) > 500:
                raise ValueError("Technical candidate text is invalid or exceeds bounds.")
        if len(self.evidence_ids) > 8 or any(not item.strip() or len(item) > 160 for item in self.evidence_ids):
            raise ValueError("Technical candidate evidence IDs exceed bounds.")
        if any(value is not None and len(value) > 240 for value in (self.parent_system, self.parent_product, self.manufacturing_family)):
            raise ValueError("Technical candidate context exceeds bounds.")


@dataclass(frozen=True)
class TechnicalDecompositionRequest:
    """Model-neutral, public-only technical interpretation contract."""

    event_id: str
    event_type: str
    canonical_customer_name: str | None
    canonical_program_name: str | None
    market: str | None
    evidence: tuple[PublicEvidenceRecord, ...]
    contract_version: str = "technical-decomposition-v1"
    prompt_version: str = "technical-decomposition-prompt-v1"

    def __post_init__(self) -> None:
        if not self.event_id.strip() or len(self.event_id) > 160:
            raise ValueError("Technical decomposition event ID is invalid.")
        if not self.evidence or len(self.evidence) > 6:
            raise ValueError("Technical decomposition requires one to six public evidence records.")


@dataclass(frozen=True)
class TechnicalDecompositionResult:
    event_summary: str
    product_candidates: tuple[TechnicalCandidate, ...] = ()
    program_candidates: tuple[TechnicalCandidate, ...] = ()
    technical_systems: tuple[TechnicalCandidate, ...] = ()
    component_candidates: tuple[TechnicalCandidate, ...] = ()
    uncertainties: tuple[str, ...] = ()
    provider: str = "gemini"
    model: str = ""

    def __post_init__(self) -> None:
        if not self.event_summary.strip() or len(self.event_summary) > 1_200:
            raise ValueError("Technical decomposition summary is invalid or exceeds bounds.")
        for collection in (self.product_candidates, self.program_candidates, self.technical_systems, self.component_candidates):
            if len(collection) > 8:
                raise ValueError("Technical decomposition list exceeds bounds.")
        if len(self.uncertainties) > 8 or any(not value.strip() or len(value) > 500 for value in self.uncertainties):
            raise ValueError("Technical decomposition uncertainty exceeds bounds.")


@dataclass(frozen=True)
class LanguageResult:
    content: str
    provider: str
    model: str
    evidence_ids: tuple[str, ...]


class LanguageProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    def interpret(self, request: IntentInterpretationRequest) -> IntentInterpretation: ...

    def synthesize(self, request: GroundedSynthesisRequest) -> LanguageResult: ...

    def decompose_technical_opportunity(
        self, request: TechnicalDecompositionRequest
    ) -> TechnicalDecompositionResult: ...
