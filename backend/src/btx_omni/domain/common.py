"""Framework-free common domain vocabulary."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum


class DataMode(StrEnum):
    SAMPLE = "SAMPLE"
    CONNECTED = "CONNECTED"
    IMPORTED = "IMPORTED"


class EvidenceState(StrEnum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"


class MatchState(StrEnum):
    EXACT_PART = "EXACT_PART"
    STRUCTURED_SIMILARITY = "STRUCTURED_SIMILARITY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    NO_MATCH = "NO_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
