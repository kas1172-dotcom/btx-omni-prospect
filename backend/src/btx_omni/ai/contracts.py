from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AiRequest:
    text: str
    evidence_ids: tuple[str, ...]
    instruction: str


@dataclass(frozen=True)
class AiResult:
    content: str
    provider: str
    model: str
    evidence_ids: tuple[str, ...]
    requires_validation: bool = True


class AiCapabilities(Protocol):
    def extract_structured_event(self, request: AiRequest) -> AiResult: ...
    def classify_event(self, request: AiRequest) -> AiResult: ...
    def resolve_ambiguity(self, request: AiRequest) -> AiResult: ...
    def summarize_evidence(self, request: AiRequest) -> AiResult: ...
    def assist_entity_resolution(self, request: AiRequest) -> AiResult: ...


class AiProvider(AiCapabilities, Protocol):
    name: str
