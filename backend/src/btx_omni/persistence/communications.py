from __future__ import annotations

import json
from datetime import UTC

from sqlalchemy import Engine, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from btx_omni.domain.communications import (
    CommunicationAuditEvent,
    CommunicationChannel,
    CommunicationDraft,
    CommunicationStatus,
)
from btx_omni.domain.work import ApprovalStatus
from btx_omni.persistence.models import (
    communication_audit_events,
    communication_drafts,
    user_preferences,
)


def _aware(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


class CommunicationVersionConflict(RuntimeError):
    pass


class SqlCommunicationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _draft(row) -> CommunicationDraft:
        return CommunicationDraft(
            id=row.id,
            account_id=row.account_id,
            channel=CommunicationChannel(row.channel),
            subject=row.subject,
            body=row.body,
            recipients=tuple(json.loads(row.recipients)),
            trigger=row.trigger,
            evidence_ids=tuple(json.loads(row.evidence_ids)),
            approval_status=ApprovalStatus(row.approval_status),
            status=CommunicationStatus(row.status),
            created_by=row.created_by,
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
            sent_at=_aware(row.sent_at),
            idempotency_key=row.idempotency_key,
            version=row.version,
        )

    def get(self, draft_id: str) -> CommunicationDraft | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(communication_drafts).where(communication_drafts.c.id == draft_id)
            ).first()
        return self._draft(row) if row else None

    def list(self) -> tuple[CommunicationDraft, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(communication_drafts).order_by(
                    communication_drafts.c.updated_at.desc()
                )
            ).all()
        return tuple(self._draft(row) for row in rows)

    def by_idempotency_key(self, key: str) -> CommunicationDraft | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(communication_drafts).where(
                    communication_drafts.c.idempotency_key == key
                )
            ).first()
        return self._draft(row) if row else None

    def save(
        self, draft: CommunicationDraft, event: CommunicationAuditEvent, *, expected_version: int | None = None
    ) -> CommunicationDraft:
        values = {
            "account_id": draft.account_id,
            "channel": draft.channel.value,
            "subject": draft.subject,
            "body": draft.body,
            "recipients": json.dumps(draft.recipients),
            "trigger": draft.trigger,
            "evidence_ids": json.dumps(draft.evidence_ids),
            "approval_status": draft.approval_status.value,
            "status": draft.status.value,
            "created_by": draft.created_by,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "sent_at": draft.sent_at,
            "idempotency_key": draft.idempotency_key or draft.id,
            "version": draft.version,
        }
        with self.engine.begin() as connection:
            if event.event == 'CREATED':
                builder = postgresql_insert if connection.dialect.name == 'postgresql' else sqlite_insert if connection.dialect.name == 'sqlite' else insert
                statement = builder(communication_drafts).values(id=draft.id, **values)
                if connection.dialect.name in {'postgresql', 'sqlite'}:
                    statement = statement.on_conflict_do_nothing()
                result = connection.execute(statement)
                if result.rowcount == 0:
                    winner = connection.execute(select(communication_drafts).where(communication_drafts.c.idempotency_key == values['idempotency_key'])).first()
                    if winner is None:
                        raise ValueError('Conflicting draft identity; inspect saved work before retrying.')
                    return self._draft(winner)
                connection.execute(insert(communication_audit_events).values(communication_id=event.communication_id,
                    actor_id=event.actor_id, event=event.event, occurred_at=event.occurred_at,
                    metadata=json.dumps(event.metadata, sort_keys=True)))
                return draft
            if expected_version is None or draft.version != expected_version + 1:
                raise CommunicationVersionConflict('A saved draft version is required before changing this communication.')
            result = connection.execute(
                    update(communication_drafts)
                    .where(communication_drafts.c.id == draft.id, communication_drafts.c.version == expected_version)
                    .values(**values)
                )
            if result.rowcount != 1:
                raise CommunicationVersionConflict('This communication changed. Refresh and compare the saved draft; your local draft has not been submitted.')
            connection.execute(
                insert(communication_audit_events).values(
                    communication_id=event.communication_id,
                    actor_id=event.actor_id,
                    event=event.event,
                    occurred_at=event.occurred_at,
                    metadata=json.dumps(event.metadata, sort_keys=True),
                )
            )
        return draft

    def append_audit(self, draft: CommunicationDraft, event: CommunicationAuditEvent) -> None:
        """A read/failed delivery receipt never writes a stale copy of the draft."""
        with self.engine.begin() as connection:
            if connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            elif connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                connection.execute(text("SET LOCAL statement_timeout = '3s'"))
            version = connection.execute(select(communication_drafts.c.version).where(
                communication_drafts.c.id == draft.id).with_for_update()).scalar_one_or_none()
            if version != draft.version:
                raise CommunicationVersionConflict('The saved communication changed during this preview. Refresh before proceeding.')
            connection.execute(insert(communication_audit_events).values(communication_id=event.communication_id,
                actor_id=event.actor_id, event=event.event, occurred_at=event.occurred_at,
                metadata=json.dumps({**event.metadata, 'draft_version': draft.version}, sort_keys=True)))

    def history(self, draft_id: str) -> tuple[CommunicationAuditEvent, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(communication_audit_events)
                .where(communication_audit_events.c.communication_id == draft_id)
                .order_by(communication_audit_events.c.id)
            ).all()
        return tuple(
            CommunicationAuditEvent(
                row.id,
                row.communication_id,
                row.actor_id,
                row.event,
                _aware(row.occurred_at),
                json.loads(row.metadata),
            )
            for row in rows
        )

    def preferences(self, user_id: str) -> dict[str, bool]:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(user_preferences).where(user_preferences.c.user_id == user_id)
            ).first()
        return {
            "compact_density": bool(row.compact_density) if row else True,
            "omni_evidence_expanded": bool(row.omni_evidence_expanded) if row else False,
        }

    def save_preferences(
        self, user_id: str, values: dict[str, bool], updated_at
    ) -> dict[str, bool]:
        current = self.preferences(user_id) | values
        with self.engine.begin() as connection:
            exists = connection.execute(
                select(user_preferences.c.user_id).where(
                    user_preferences.c.user_id == user_id
                )
            ).scalar_one_or_none()
            payload = {**current, "updated_at": updated_at}
            if exists:
                connection.execute(
                    update(user_preferences)
                    .where(user_preferences.c.user_id == user_id)
                    .values(**payload)
                )
            else:
                connection.execute(
                    insert(user_preferences).values(user_id=user_id, **payload)
                )
        return current
