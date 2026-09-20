from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from btx_omni.domain.common import require_aware


class ActionStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class ActionPriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PrincipalRole(StrEnum):
    SALESPERSON = "SALESPERSON"
    MANAGER = "MANAGER"


@dataclass(frozen=True)
class Principal:
    user_id: str
    display_name: str
    role: PrincipalRole
    tenant_id: str | None = None


@dataclass(frozen=True)
class Action:
    id: str
    account_id: str
    title: str
    description: str | None
    owner_id: str | None
    priority: ActionPriority
    due_date: date | None
    status: ActionStatus
    approval_status: ApprovalStatus
    source_suggestion_id: str | None
    evidence_ids: tuple[str, ...]
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    canceled_at: datetime | None = None
    version: int = 1
    context_referents: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        require_aware(self.updated_at, "updated_at")
        if self.completed_at:
            require_aware(self.completed_at, "completed_at")
        if self.canceled_at:
            require_aware(self.canceled_at, "canceled_at")
        if not self.title.strip():
            raise ValueError("Action title is required.")
        if self.version < 1:
            raise ValueError("Action version must be positive.")

    @property
    def summary(self) -> str:
        """Read compatibility for the bounded Omni contract during convergence."""
        return self.title

    @property
    def notes(self) -> str | None:
        return self.description


@dataclass(frozen=True)
class ActionAuditEvent:
    id: int | None
    action_id: str
    actor_id: str
    event: str
    occurred_at: datetime
    metadata: dict[str, object]

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
