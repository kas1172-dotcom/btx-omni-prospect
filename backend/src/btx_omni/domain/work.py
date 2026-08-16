from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from btx_omni.domain.common import require_aware


class ActionState(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"
    COMPLETED = "COMPLETED"


class ActionType(StrEnum):
    REVIEW = "REVIEW"
    ASSIGN = "ASSIGN"
    APPROVE = "APPROVE"
    DISMISS = "DISMISS"
    FOLLOW_UP = "FOLLOW_UP"
    CRM_ACTION = "CRM_ACTION"


@dataclass(frozen=True)
class WorkItem:
    """Backend work queue item; it does not imply a top-level POC surface."""

    id: str
    account_id: str
    summary: str
    state: ActionState
    evidence_ids: tuple[str, ...]
    owner_id: str | None = None


@dataclass(frozen=True)
class GovernedAction:
    id: str
    account_id: str
    action_type: ActionType
    state: ActionState
    summary: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    created_at: datetime
    requires_human_confirmation: bool

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        if not self.evidence_ids:
            raise ValueError("governed actions require evidence")


@dataclass(frozen=True)
class ActionAuditEvent:
    action_id: str
    actor_id: str
    event: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
