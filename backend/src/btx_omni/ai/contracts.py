from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GroundedSynthesisRequest:
    question: str
    governed_answer: str
    evidence_ids: tuple[str, ...]
    missingness: tuple[str, ...]


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

    def synthesize(self, request: GroundedSynthesisRequest) -> LanguageResult: ...
