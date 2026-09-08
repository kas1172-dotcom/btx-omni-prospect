from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from btx_omni.domain.common import require_aware
from btx_omni.domain.work import ApprovalStatus


class CommunicationChannel(StrEnum):
    EMAIL = "EMAIL"


class CommunicationStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class CommunicationDraft:
    id: str
    account_id: str
    channel: CommunicationChannel
    subject: str
    body: str
    recipients: tuple[str, ...]
    created_by: str
    created_at: datetime
    updated_at: datetime
    approval_status: ApprovalStatus
    status: CommunicationStatus
    trigger: str | None = None
    evidence_ids: tuple[str, ...] = ()
    idempotency_key: str | None = None
    sent_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 1:
            raise ValueError("Communication version must be a positive integer.")
        require_aware(self.created_at, "created_at")
        require_aware(self.updated_at, "updated_at")
        if self.sent_at:
            require_aware(self.sent_at, "sent_at")
        if not self.subject.strip() or not self.body.strip():
            raise ValueError("Communication subject and body are required.")


@dataclass(frozen=True)
class CommunicationAuditEvent:
    id: int | None
    communication_id: str
    actor_id: str
    event: str
    occurred_at: datetime
    metadata: dict[str, object]

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
