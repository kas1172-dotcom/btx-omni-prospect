from __future__ import annotations

import json
from datetime import UTC, date

from sqlalchemy import Engine, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from btx_omni.domain.work import (
    Action,
    ActionAuditEvent,
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
)
from btx_omni.persistence.models import (
    action_suggestion_decisions,
    work_audit_events,
    work_items,
)


class SqlActionRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _action(row) -> Action:
        def aware(value):
            return (
                value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
            )

        return Action(
            id=row.id,
            account_id=row.account_id,
            title=row.summary,
            description=row.description,
            owner_id=row.owner_id,
            priority=ActionPriority(row.priority),
            due_date=date.fromisoformat(row.due_date) if row.due_date else None,
            status=ActionStatus(row.status),
            approval_status=ApprovalStatus(row.approval_status),
            source_suggestion_id=row.source_suggestion_id,
            evidence_ids=tuple(json.loads(row.evidence_ids)),
            created_by=row.created_by,
            created_at=aware(row.created_at),
            updated_at=aware(row.updated_at),
            completed_at=aware(row.completed_at),
            canceled_at=aware(row.canceled_at),
            version=row.version,
            context_referents=tuple(tuple(item) for item in json.loads(row.context_referents or "[]")),
        )

    def get(self, action_id: str) -> Action | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(work_items).where(work_items.c.id == action_id)
            ).first()
        return self._action(row) if row else None

    def by_suggestion(self, suggestion_id: str) -> Action | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(work_items).where(
                    work_items.c.source_suggestion_id == suggestion_id
                )
            ).first()
        return self._action(row) if row else None

    def list(self) -> tuple[Action, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(work_items)).all()
        return tuple(self._action(row) for row in rows)

    def save(self, action: Action, event: ActionAuditEvent, expected_version: int | None = None) -> Action:
        values = {
            "account_id": action.account_id,
            "summary": action.title,
            "description": action.description,
            "owner_id": action.owner_id,
            "priority": action.priority.value,
            "due_date": action.due_date.isoformat() if action.due_date else None,
            "status": action.status.value,
            "approval_status": action.approval_status.value,
            "source_suggestion_id": action.source_suggestion_id,
            "evidence_ids": json.dumps(action.evidence_ids),
            "context_referents": json.dumps(action.context_referents),
            "created_by": action.created_by,
            "created_at": action.created_at,
            "updated_at": action.updated_at,
            "completed_at": action.completed_at,
            "canceled_at": action.canceled_at,
            "version": action.version,
            "idempotency_key": action.id,
        }
        with self.engine.begin() as connection:
            if event.event != "CREATED":
                statement = update(work_items).where(work_items.c.id == action.id)
                if expected_version is not None:
                    statement = statement.where(work_items.c.version == expected_version)
                result = connection.execute(statement.values(**values))
                if result.rowcount != 1:
                    raise ValueError("Action has changed; reload it before saving.")
                connection.execute(
                    insert(work_audit_events).values(
                        work_item_id=event.action_id, event=event.event,
                        actor_id=event.actor_id, occurred_at=event.occurred_at,
                        note=None, metadata=json.dumps(event.metadata, sort_keys=True),
                    )
                )
                return action
            statement = (
                postgresql_insert(work_items)
                if connection.dialect.name == "postgresql"
                else sqlite_insert(work_items)
                if connection.dialect.name == "sqlite"
                else insert(work_items)
            )
            result = connection.execute(
                statement.values(id=action.id, **values).on_conflict_do_nothing(
                    index_elements=[work_items.c.id]
                )
                if connection.dialect.name in {"postgresql", "sqlite"}
                else statement.values(id=action.id, **values)
            )
            if result.rowcount == 0:
                row = connection.execute(select(work_items).where(work_items.c.id == action.id)).first()
                return self._action(row)
            connection.execute(
                insert(work_audit_events).values(
                    work_item_id=event.action_id,
                    event=event.event,
                    actor_id=event.actor_id,
                    occurred_at=event.occurred_at,
                    note=None,
                    metadata=json.dumps(event.metadata, sort_keys=True),
                )
            )
        return action

    def history(self, action_id: str) -> tuple[ActionAuditEvent, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(work_audit_events)
                .where(work_audit_events.c.work_item_id == action_id)
                .order_by(work_audit_events.c.id)
            ).all()
        return tuple(
            ActionAuditEvent(
                row.id,
                row.work_item_id,
                row.actor_id,
                row.event,
                row.occurred_at.replace(tzinfo=UTC)
                if row.occurred_at.tzinfo is None
                else row.occurred_at,
                json.loads(row.metadata or "{}"),
            )
            for row in rows
        )

    def dismiss_suggestion(
        self, suggestion_id: str, actor_id: str, occurred_at
    ) -> None:
        with self.engine.begin() as connection:
            if (
                connection.execute(
                    select(action_suggestion_decisions.c.suggestion_id).where(
                        action_suggestion_decisions.c.suggestion_id == suggestion_id
                    )
                ).scalar_one_or_none()
                is None
            ):
                connection.execute(
                    insert(action_suggestion_decisions).values(
                        suggestion_id=suggestion_id,
                        dismissed_by=actor_id,
                        dismissed_at=occurred_at,
                    )
                )

    def dismissed_suggestions(self) -> frozenset[str]:
        with self.engine.connect() as connection:
            return frozenset(
                connection.execute(
                    select(action_suggestion_decisions.c.suggestion_id)
                ).scalars()
            )
