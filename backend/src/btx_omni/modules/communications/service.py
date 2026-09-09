from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from btx_omni.domain.communications import (
    CommunicationAuditEvent,
    CommunicationChannel,
    CommunicationDraft,
    CommunicationStatus,
)
from btx_omni.domain.work import ApprovalStatus, Principal, PrincipalRole
from btx_omni.integrations.communications import CommunicationDeliveryPort
from btx_omni.persistence.communications import SqlCommunicationRepository


class CommunicationNotFoundError(LookupError):
    pass


class CommunicationForbiddenError(PermissionError):
    pass


class CommunicationConflictError(RuntimeError):
    pass


class CommunicationService:
    def __init__(self, repository: SqlCommunicationRepository) -> None:
        self.repository = repository

    def _get(self, draft_id: str) -> CommunicationDraft:
        draft = self.repository.get(draft_id)
        if not draft:
            raise CommunicationNotFoundError(draft_id)
        return draft

    @staticmethod
    def _can_manage(principal: Principal, draft: CommunicationDraft) -> bool:
        return principal.role is PrincipalRole.MANAGER or draft.created_by == principal.user_id

    def list(self, principal: Principal) -> tuple[CommunicationDraft, ...]:
        drafts = self.repository.list()
        return drafts if principal.role is PrincipalRole.MANAGER else tuple(
            item for item in drafts if item.created_by == principal.user_id
        )

    def create(
        self,
        *,
        account_id: str,
        subject: str,
        body: str,
        recipients: tuple[str, ...],
        principal: Principal,
        occurred_at: datetime,
        trigger: str | None = None,
        evidence_ids: tuple[str, ...] = (),
        idempotency_key: str | None = None,
    ) -> CommunicationDraft:
        request_key = idempotency_key or str(uuid4())
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
            raise ValueError('Communication retry key must be bounded.')
        fingerprint = self._creation_fingerprint(account_id, subject, body, recipients, trigger, evidence_ids)
        key = 'comm-create-v2:' + sha256(json.dumps([principal.user_id, request_key]).encode()).hexdigest()
        if existing := self.repository.by_idempotency_key(key):
            return self._creation_replay(existing, principal, fingerprint)
        # A legacy raw key never grants access to another user's draft. Preserve
        # only provably same-actor, same-content legacy retries.
        legacy = self.repository.by_idempotency_key(request_key)
        if legacy and legacy.created_by == principal.user_id:
            return self._creation_replay(legacy, principal, fingerprint)
        draft = CommunicationDraft(
            str(uuid4()), account_id, CommunicationChannel.EMAIL, subject.strip(),
            body.strip(), recipients, principal.user_id, occurred_at, occurred_at,
            ApprovalStatus.PENDING, CommunicationStatus.DRAFT, trigger,
            evidence_ids, key,
        )
        saved = self.repository.save(
            draft,
            CommunicationAuditEvent(None, draft.id, principal.user_id, "CREATED", occurred_at, {"status": "DRAFT", "creation_fingerprint": fingerprint}),
        )
        return self._creation_replay(saved, principal, fingerprint)

    @staticmethod
    def _creation_fingerprint(account_id, subject, body, recipients, trigger, evidence_ids):
        return sha256(json.dumps([account_id, subject.strip(), body.strip(), list(recipients), trigger, list(evidence_ids)],
                                 ensure_ascii=False).encode()).hexdigest()

    def _creation_replay(self, existing, principal, fingerprint):
        if existing.created_by != principal.user_id:
            raise CommunicationConflictError('This retry does not belong to the current user.')
        created = next((event for event in self.repository.history(existing.id) if event.event == 'CREATED'), None)
        original = created.metadata.get('creation_fingerprint') if created else None
        if original is None:
            original = self._creation_fingerprint(existing.account_id, existing.subject, existing.body,
                                                   existing.recipients, existing.trigger, existing.evidence_ids)
        if original != fingerprint:
            raise CommunicationConflictError('This retry key belongs to different draft content; inspect the saved draft before creating another.')
        return existing

    def edit(
        self,
        draft_id: str,
        *,
        principal: Principal,
        occurred_at: datetime,
        subject: str | None = None,
        body: str | None = None,
        recipients: tuple[str, ...] | None = None,
        ai_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> CommunicationDraft:
        draft = self._get(draft_id)
        if not self._can_manage(principal, draft):
            raise CommunicationForbiddenError("This draft is outside the current principal's permitted work.")
        self._check_version(draft, expected_version)
        if draft.status not in {CommunicationStatus.DRAFT, CommunicationStatus.READY}:
            raise CommunicationConflictError("Only an unsent communication can be edited.")
        updated = replace(
            draft,
            subject=(subject if subject is not None else draft.subject).strip(),
            body=(body if body is not None else draft.body).strip(),
            recipients=recipients if recipients is not None else draft.recipients,
            approval_status=ApprovalStatus.PENDING,
            status=CommunicationStatus.DRAFT,
            updated_at=occurred_at,
            version=draft.version + 1,
        )
        return self.repository.save(
            updated,
            CommunicationAuditEvent(None, draft.id, principal.user_id, "AI_REVISED" if ai_metadata else "EDITED", occurred_at, ai_metadata or {}),
            expected_version=draft.version,
        )

    @staticmethod
    def _check_version(draft, expected_version):
        if expected_version is not None and draft.version != expected_version:
            raise CommunicationConflictError('This communication changed. Refresh and compare the saved version before retrying; your local draft remains unchanged.')

    def decide(self, draft_id: str, decision: ApprovalStatus, *, principal: Principal, occurred_at: datetime, expected_version: int | None = None) -> CommunicationDraft:
        if principal.role is not PrincipalRole.MANAGER:
            raise CommunicationForbiddenError("Manager authorization is required for communication review.")
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            raise CommunicationConflictError("Approval decision must be APPROVED or REJECTED.")
        draft = self._get(draft_id)
        self._check_version(draft, expected_version)
        if draft.status not in {CommunicationStatus.DRAFT, CommunicationStatus.READY}:
            raise CommunicationConflictError('Only an unsent communication may be reviewed.')
        updated = replace(draft, approval_status=decision, status=CommunicationStatus.READY if decision is ApprovalStatus.APPROVED else CommunicationStatus.DRAFT, updated_at=occurred_at, version=draft.version + 1)
        return self.repository.save(updated, CommunicationAuditEvent(None, draft.id, principal.user_id, decision.value, occurred_at, {"approval_status": decision.value, 'reviewed_version': draft.version}), expected_version=draft.version)

    def preview(self, draft_id: str, *, principal: Principal, occurred_at: datetime, delivery: CommunicationDeliveryPort):
        draft = self._get(draft_id)
        if not self._can_manage(principal, draft):
            raise CommunicationForbiddenError("This draft is outside the current principal's permitted work.")
        preview = delivery.preview(draft)
        self.repository.append_audit(draft, CommunicationAuditEvent(None, draft.id, principal.user_id, "DELIVERY_PREVIEWED", occurred_at, {"available": preview.available, "provider": preview.provider}))
        return preview

    def send(self, draft_id: str, *, principal: Principal, occurred_at: datetime, confirmed: bool, idempotency_key: str, delivery: CommunicationDeliveryPort, expected_version: int | None = None):
        if not confirmed:
            raise CommunicationConflictError("Explicit human confirmation is required before delivery.")
        draft = self._get(draft_id)
        if not self._can_manage(principal, draft):
            raise CommunicationForbiddenError("This draft is outside the current principal's permitted work.")
        if draft.status is CommunicationStatus.SENT:
            return draft
        self._check_version(draft, expected_version)
        if draft.approval_status is not ApprovalStatus.APPROVED:
            raise CommunicationConflictError("Approved human review is required before delivery.")
        if not draft.recipients:
            raise CommunicationConflictError("No verified deliverable recipient is available.")
        try:
            receipt = delivery.send(draft, idempotency_key=idempotency_key)
        except Exception:
            self.repository.append_audit(draft, CommunicationAuditEvent(None, draft.id, principal.user_id, "DELIVERY_BLOCKED", occurred_at, {"reason": "PROVIDER_UNAVAILABLE"}))
            raise
        sent = replace(draft, status=CommunicationStatus.SENT, sent_at=occurred_at, updated_at=occurred_at, version=draft.version + 1)
        self.repository.save(sent, CommunicationAuditEvent(None, draft.id, principal.user_id, "DELIVERED", occurred_at, {"receipt": receipt}), expected_version=draft.version)
        return sent

    def history(self, draft_id: str, principal: Principal):
        draft = self._get(draft_id)
        if not self._can_manage(principal, draft):
            raise CommunicationForbiddenError("This draft is outside the current principal's permitted work.")
        return self.repository.history(draft_id)
