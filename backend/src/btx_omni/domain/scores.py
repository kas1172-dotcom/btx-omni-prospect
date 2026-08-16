from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from btx_omni.domain.common import require_aware


class ScoreStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HYPOTHESIS = "HYPOTHESIS"


@dataclass(frozen=True)
class ScoreConfiguration:
    id: str
    version: str
    hypothesis: bool
    interpretation_note: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")


@dataclass(frozen=True)
class ScoreAssessment:
    id: str
    account_id: str
    configuration_id: str
    status: ScoreStatus
    score: Decimal | None
    coverage: Decimal
    evidence_ids: tuple[str, ...]
    missing_fields: tuple[str, ...]
    calculated_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.calculated_at, "calculated_at")
        if self.status is ScoreStatus.AVAILABLE and self.score is None:
            raise ValueError("available scores require a value")


@dataclass(frozen=True)
class AccountAttractiveness:
    account_id: str
    status: ScoreStatus
    score: Decimal | None
    configuration_version: str
    evidence_ids: tuple[str, ...]
    missing_fields: tuple[str, ...]
    calculated_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.calculated_at, "calculated_at")
        if self.status is ScoreStatus.AVAILABLE and self.score is None:
            raise ValueError("available scores require a value")
        if self.score is not None and not Decimal(0) <= self.score <= Decimal(1):
            raise ValueError("score must be between zero and one")


@dataclass(frozen=True)
class ExternalIndustryRank:
    account_id: str
    industry: str
    rank: int
    source: str
    methodology: str

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("external rank must be positive")
