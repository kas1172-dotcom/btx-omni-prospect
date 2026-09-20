from __future__ import annotations

from dataclasses import dataclass, field
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
    REQUESTED = "REQUESTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


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
class Subtask:
    id: str
    parent_id: str
    title: str
    done: bool = False
    due_date: date | None = None
    owner_id: str | None = None
    removed: bool = False

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Subtask title is required.")


@dataclass(frozen=True)
class Action:
    id: str
    account_id: str | None
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
    previous_status: ActionStatus | None = None
    approval_requested_by: str | None = None
    approval_comment: str | None = None
    subtasks: tuple[Subtask, ...] = ()
    allowed_transitions: tuple[ActionStatus, ...] = field(init=False)

    def __post_init__(self) -> None:
        # This is the only work-state transition definition. Serialized to clients.
        transitions = {
            ActionStatus.OPEN: (ActionStatus.IN_PROGRESS, ActionStatus.COMPLETED, ActionStatus.CANCELED),
            ActionStatus.IN_PROGRESS: (ActionStatus.COMPLETED, ActionStatus.CANCELED),
            ActionStatus.COMPLETED: (ActionStatus.IN_PROGRESS,),
            ActionStatus.CANCELED: (self.previous_status,) if self.previous_status else (),
        }
        object.__setattr__(self, "allowed_transitions", transitions[self.status])
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

    def is_overdue(self, today: date) -> bool:
        return bool(self.due_date and self.due_date < today and self.status in {ActionStatus.OPEN, ActionStatus.IN_PROGRESS})

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
