"""Governed, idempotent action lifecycle with no autonomous external writes."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256

from btx_omni.domain.common import require_aware
from btx_omni.integrations.hubspot.contracts import (
    CrmActionPreview,
    SampleHubSpotAdapter,
)


class WorkStatus(StrEnum):
    PROPOSED = "PROPOSED"
    IN_REVIEW = "IN_REVIEW"
    ASSIGNED = "ASSIGNED"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"
    FOLLOW_UP = "FOLLOW_UP"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class GovernedWorkItem:
    id: str
    account_id: str
    opportunity_id: str | None
    status: WorkStatus
    summary: str
    evidence_ids: tuple[str, ...]
    owner_id: str | None
    priority: str
    due_date: date | None
    notes: str | None
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True)
class WorkAuditEvent:
    work_item_id: str
    event: str
    actor_id: str
    occurred_at: datetime
    note: str | None = None


class WorkService:
    def __init__(self) -> None:
        self._items: dict[str, GovernedWorkItem] = {}
        self._keys: dict[str, str] = {}
        self._audit: list[WorkAuditEvent] = []

    def create(self, *, account_id: str, summary: str, evidence_ids: tuple[str, ...], idempotency_key: str, actor_id: str, occurred_at: datetime, opportunity_id: str | None = None, owner_id: str | None = None, priority: str = "MEDIUM", due_date: date | None = None, notes: str | None = None) -> GovernedWorkItem:
        require_aware(occurred_at, "occurred_at")
        if not evidence_ids:
            raise ValueError("work items require evidence")
        existing = self._keys.get(idempotency_key)
        if existing:
            return self._items[existing]
        identifier = f"work-{sha256(idempotency_key.encode()).hexdigest()[:20]}"
        item = GovernedWorkItem(identifier, account_id, opportunity_id, WorkStatus.PROPOSED, summary, evidence_ids, owner_id, priority, due_date, notes, idempotency_key, occurred_at)
        self._items[identifier], self._keys[idempotency_key] = item, identifier
        self._audit.append(WorkAuditEvent(identifier, "CREATED", actor_id, occurred_at, notes))
        return item

    def transition(self, item_id: str, status: WorkStatus, *, actor_id: str, occurred_at: datetime, owner_id: str | None = None, note: str | None = None) -> GovernedWorkItem:
        require_aware(occurred_at, "occurred_at")
        item = self._items[item_id]
        updated = replace(item, status=status, owner_id=owner_id if owner_id is not None else item.owner_id, notes=note if note is not None else item.notes)
        self._items[item_id] = updated
        self._audit.append(WorkAuditEvent(item_id, status.value, actor_id, occurred_at, note))
        return updated

    def preview_crm_action(self, item_id: str, crm: SampleHubSpotAdapter) -> CrmActionPreview:
        item = self._items[item_id]
        return crm.preview_action(item.id, item.account_id, "CREATE_FOLLOW_UP", {"summary": item.summary, "owner_id": item.owner_id or ""})

    def confirm_and_execute_crm_action(self, preview: CrmActionPreview, crm: SampleHubSpotAdapter) -> CrmActionPreview:
        return crm.execute_action(replace(preview, confirmed=True))

    def audit(self, item_id: str) -> tuple[WorkAuditEvent, ...]:
        return tuple(item for item in self._audit if item.work_item_id == item_id)
