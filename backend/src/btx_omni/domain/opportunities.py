from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OpportunityState(StrEnum):
    QUALIFY = "QUALIFY"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class Opportunity:
    id: str
    account_id: str
    state: OpportunityState
    title: str
    estimated_value_minor: int | None
    currency: str
    evidence_ids: tuple[str, ...]
