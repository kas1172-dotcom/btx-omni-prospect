"""Durable, authorized Action workflow; Suggestions remain separate projections."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from hashlib import sha256
from typing import Protocol

from btx_omni.domain.work import (
    Action,
    ActionAuditEvent,
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
    Principal,
    PrincipalRole,
)


class ActionNotFoundError(KeyError):
    pass


class ActionConflictError(ValueError):
    pass


class ActionForbiddenError(PermissionError):
    pass


class ActionRepository(Protocol):
    def transact_audit(self, action_id: str, operation): ...
    def get(self, action_id: str) -> Action | None: ...
    def by_suggestion(self, suggestion_id: str) -> Action | None: ...
    def list(self) -> tuple[Action, ...]: ...
    def save(self, action: Action, event: ActionAuditEvent, expected_version: int | None = None) -> Action: ...
    def history(self, action_id: str) -> tuple[ActionAuditEvent, ...]: ...
    def dismiss_suggestion(
        self, suggestion_id: str, actor_id: str, occurred_at: datetime
    ) -> None: ...
    def dismissed_suggestions(self, actor_id: str | None = None) -> frozenset[str]: ...


class MemoryActionRepository:
    """Deterministic unit-test repository; production runtime uses SQL."""

    def __init__(self) -> None:
        self.items: dict[str, Action] = {}
        self.events: list[ActionAuditEvent] = []
        self.dismissed: set[str] = set()
        self.dismissed_actors: dict[str, str] = {}

    def get(self, action_id: str) -> Action | None:
        return self.items.get(action_id)

    def transact_audit(self, action_id: str, operation):
        action = self.get(action_id)
        if action is None:
            raise ActionNotFoundError(action_id)
        event, result = operation(action, self.history(action_id))
        if event is not None:
            self.events.append(event)
        return result

    def by_suggestion(self, suggestion_id: str) -> Action | None:
        return next(
            (x for x in self.items.values() if x.source_suggestion_id == suggestion_id),
            None,
        )

    def list(self) -> tuple[Action, ...]:
        return tuple(self.items.values())

    def save(self, action: Action, event: ActionAuditEvent, expected_version: int | None = None) -> Action:
        current = self.items.get(action.id)
        if expected_version is not None and (not current or current.version != expected_version):
            raise ActionConflictError("Action has changed; reload it before saving.")
        self.items[action.id] = action
        self.events.append(event)
        return action

    def history(self, action_id: str) -> tuple[ActionAuditEvent, ...]:
        return tuple(x for x in self.events if x.action_id == action_id)

    def dismiss_suggestion(
        self, suggestion_id: str, actor_id: str, occurred_at: datetime
    ) -> None:
        self.dismissed.add(suggestion_id)
        self.dismissed_actors[suggestion_id] = actor_id

    def dismissed_suggestions(self, actor_id: str | None = None) -> frozenset[str]:
        return frozenset(sid for sid in self.dismissed if actor_id is None or self.dismissed_actors.get(sid) == actor_id)


class ActionPolicy:
    @staticmethod
    def require_manage(principal: Principal, action: Action) -> None:
        if principal.role is PrincipalRole.MANAGER:
            return
        if (
            action.owner_id not in {None, principal.user_id}
            and action.created_by != principal.user_id
        ):
            raise ActionForbiddenError(
                "This Action is outside the current principal's permitted work."
            )

    @staticmethod
    def require_manager(principal: Principal) -> None:
        if principal.role is not PrincipalRole.MANAGER:
            raise ActionForbiddenError("Manager authorization is required.")


ALLOWED_TRANSITIONS = {
    ActionStatus.OPEN: {ActionStatus.IN_PROGRESS, ActionStatus.CANCELED},
    ActionStatus.IN_PROGRESS: {ActionStatus.COMPLETED, ActionStatus.CANCELED},
    ActionStatus.COMPLETED: set(),
    ActionStatus.CANCELED: set(),
}


class WorkService:
    def __init__(self, repository: ActionRepository | None = None) -> None:
        self.repository = repository or MemoryActionRepository()

    def create(
        self,
        *,
        account_id: str,
        occurred_at: datetime,
        title: str | None = None,
        principal: Principal | None = None,
        summary: str | None = None,
        actor_id: str | None = None,
        description: str | None = None,
        owner_id: str | None = None,
        priority: ActionPriority = ActionPriority.MEDIUM,
        due_date: date | None = None,
        evidence_ids: tuple[str, ...] = (),
        context_referents: tuple[tuple[str, str], ...] = (),
        source_suggestion_id: str | None = None,
        approval_required: bool = False,
        idempotency_key: str | None = None,
    ) -> Action:
        title = title or summary or ""
        if principal is None:
            from btx_omni.core.config import Settings
            from btx_omni.security.sessions import server_principal
            principal = server_principal(Settings(), actor_id or "seller-1", actor_id or "Salesperson", PrincipalRole.SALESPERSON)
        priority = ActionPriority(priority)
        if owner_id and owner_id != principal.user_id:
            ActionPolicy.require_manager(principal)
        if source_suggestion_id:
            existing = self.repository.by_suggestion(source_suggestion_id)
            if existing:
                ActionPolicy.require_manage(principal, existing)
                if existing.account_id != account_id:
                    raise ActionConflictError("Suggestion belongs to a different account.")
                return existing
        key = (
            idempotency_key
            or f"{principal.user_id}:{account_id}:{title}:{occurred_at.isoformat()}"
        )
        identifier = f"action-{sha256(key.encode()).hexdigest()[:20]}"
        fingerprint = None
        if idempotency_key:
            fingerprint = self._creation_fingerprint(
                account_id, title.strip(), description, owner_id or principal.user_id,
                priority, due_date, evidence_ids, context_referents,
                source_suggestion_id, approval_required,
            )
            # Preserve eligible legacy retries without sharing a caller's key namespace.
            legacy = self.repository.get(identifier)
            if legacy and legacy.created_by == principal.user_id and legacy.account_id == account_id:
                return self._creation_replay(legacy, principal, fingerprint)
            scoped_key = json.dumps(["action-create-v2", principal.user_id, account_id, key])
            identifier = f"action-{sha256(scoped_key.encode()).hexdigest()[:20]}"
        existing = self.repository.get(identifier)
        if existing:
            return self._creation_replay(existing, principal, fingerprint)
        action = Action(
            identifier,
            account_id,
            title.strip(),
            description,
            owner_id or principal.user_id,
            priority,
            due_date,
            ActionStatus.OPEN,
            ApprovalStatus.PENDING
            if approval_required
            else ApprovalStatus.NOT_REQUIRED,
            source_suggestion_id,
            evidence_ids,
            principal.user_id,
            occurred_at,
            occurred_at,
            version=1,
            context_referents=context_referents,
        )
        saved = self.repository.save(
            action,
            self._event(
                action.id,
                principal,
                "CREATED",
                occurred_at,
                {"status": action.status.value, **(
                    {"creation_fingerprint": fingerprint} if fingerprint else {}
                )},
            ),
        )
        # SQL insert-on-conflict may return a concurrent creator's committed row.
        if saved.account_id != account_id:
            raise ActionConflictError("Suggestion belongs to a different account.")
        return self._creation_replay(saved, principal, fingerprint)

    @staticmethod
    def _creation_fingerprint(
        account_id, title, description, owner_id, priority, due_date,
        evidence_ids, context_referents, source_suggestion_id, approval_required,
    ) -> str:
        payload = [account_id, title, description, owner_id, str(priority),
                   due_date.isoformat() if due_date else None, sorted(evidence_ids),
                   sorted(context_referents), source_suggestion_id, approval_required]
        return sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()

    def _creation_replay(
        self, action: Action, principal: Principal, fingerprint: str | None,
    ) -> Action:
        ActionPolicy.require_manage(principal, action)
        if fingerprint:
            original = next((event.metadata.get("creation_fingerprint")
                             for event in self.repository.history(action.id)
                             if event.event == "CREATED"), None)
            if original is None and action.version == 1:
                original = self._creation_fingerprint(
                    action.account_id, action.title, action.description, action.owner_id,
                    action.priority, action.due_date, action.evidence_ids,
                    action.context_referents, action.source_suggestion_id,
                    action.approval_status is ApprovalStatus.PENDING,
                )
            if original != fingerprint:
                raise ActionConflictError(
                    "Retry does not match the original proposal; inspect existing work before retrying."
                )
        return action

    def get(self, action_id: str) -> Action:
        action = self.repository.get(action_id)
        if not action:
            raise ActionNotFoundError(action_id)
        return action

    def list(self, principal: Principal | None = None) -> tuple[Action, ...]:
        items = self.repository.list()
        if principal and principal.role is PrincipalRole.SALESPERSON:
            items = tuple(
                x
                for x in items
                if x.owner_id in {None, principal.user_id}
                or x.created_by == principal.user_id
            )
        rank = {ActionPriority.HIGH: 0, ActionPriority.MEDIUM: 1, ActionPriority.LOW: 2}
        return tuple(
            sorted(
                items,
                key=lambda x: (rank[x.priority], x.due_date or date.max, x.created_at),
            )
        )

    def edit(
        self,
        action_id: str,
        *,
        principal: Principal,
        occurred_at: datetime,
        expected_version: int | None = None,
        **changes: object,
    ) -> Action:
        action = self.get(action_id)
        ActionPolicy.require_manage(principal, action)
        owner_id = changes.get("owner_id", action.owner_id)
        if owner_id != action.owner_id:
            ActionPolicy.require_manager(principal)
        permitted = {
            k: v
            for k, v in changes.items()
            if k in {"title", "description", "owner_id", "priority", "due_date"}
            and v != getattr(action, k)
        }
        if not permitted:
            return action
        self._require_version(action, expected_version)
        updated = replace(action, **permitted, updated_at=occurred_at, version=action.version + 1)
        metadata = {
            k: {"before": self._json(getattr(action, k)), "after": self._json(v)}
            for k, v in permitted.items()
        }
        return self.repository.save(
            updated,
            self._event(
                action.id, principal, "EDITED", occurred_at, {"changes": metadata}
            ), expected_version=action.version,
        )

    def transition(
        self,
        action_id: str,
        status: ActionStatus,
        *,
        principal: Principal,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> Action:
        action = self.get(action_id)
        ActionPolicy.require_manage(principal, action)
        self._require_version(action, expected_version)
        if status not in ALLOWED_TRANSITIONS[action.status]:
            raise ActionConflictError(
                f"{action.status.value} cannot transition to {status.value}."
            )
        updated = replace(
            action,
            status=status,
            updated_at=occurred_at,
            completed_at=occurred_at
            if status is ActionStatus.COMPLETED
            else action.completed_at,
            canceled_at=occurred_at
            if status is ActionStatus.CANCELED
            else action.canceled_at,
            version=action.version + 1,
        )
        return self.repository.save(
            updated,
            self._event(
                action.id,
                principal,
                "STATUS_CHANGED",
                occurred_at,
                {"before": action.status.value, "after": status.value},
            ), expected_version=action.version,
        )

    def decide_approval(
        self,
        action_id: str,
        decision: ApprovalStatus,
        *,
        principal: Principal,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> Action:
        ActionPolicy.require_manager(principal)
        action = self.get(action_id)
        self._require_version(action, expected_version)
        if action.approval_status is not ApprovalStatus.PENDING or decision not in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
        }:
            raise ActionConflictError("This Action has no pending approval decision.")
        updated = replace(action, approval_status=decision, updated_at=occurred_at, version=action.version + 1)
        return self.repository.save(
            updated,
            self._event(
                action.id,
                principal,
                "APPROVAL_DECIDED",
                occurred_at,
                {"before": action.approval_status.value, "after": decision.value},
            ), expected_version=action.version,
        )

    def audit(self, action_id: str) -> tuple[ActionAuditEvent, ...]:
        self.get(action_id)
        return self.repository.history(action_id)

    def dismiss_suggestion(
        self, suggestion_id: str, *, principal: Principal, occurred_at: datetime
    ) -> None:
        self.repository.dismiss_suggestion(
            suggestion_id, principal.user_id, occurred_at
        )

    def dismissed_suggestions(self, actor_id: str | None = None) -> frozenset[str]:
        return self.repository.dismissed_suggestions(actor_id)

    @staticmethod
    def _event(
        action_id: str,
        principal: Principal,
        event: str,
        occurred_at: datetime,
        metadata: dict[str, object],
    ) -> ActionAuditEvent:
        return ActionAuditEvent(
            None, action_id, principal.user_id, event, occurred_at, metadata
        )

    @staticmethod
    def _json(value: object) -> object:
        return (
            value.value
            if hasattr(value, "value")
            else value.isoformat()
            if isinstance(value, (date, datetime))
            else value
        )

    @staticmethod
    def _require_version(action: Action, expected_version: int | None) -> None:
        if expected_version is not None and action.version != expected_version:
            raise ActionConflictError("Action has changed; reload it before saving.")


WorkStatus = ActionStatus
