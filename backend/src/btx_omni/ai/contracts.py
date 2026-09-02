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
