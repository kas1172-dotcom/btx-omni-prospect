"""Immutable user-scoped suggestion feedback; never a score or task-state write."""
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    insert,
    select,
    text,
)

from btx_omni.persistence.models import action_suggestion_decisions, metadata

work_suggestion_feedback = Table(
    'work_suggestion_feedback', metadata,
    Column('id', String(36), primary_key=True),
    Column('user_id', String(128), nullable=False),
    Column('suggestion_id', String(160), nullable=False),
    Column('account_id', String(64), nullable=False),
    Column('version', Integer, nullable=False),
    Column('reason', String(32), nullable=False),
    Column('note', Text, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('snooze_until', DateTime(timezone=True)),
    Column('previous_feedback_id', String(36)),
    Column('idempotency_key', String(64), nullable=False),
    Column('request_hash', String(64), nullable=False),
    Column('source_revision', String(64)),
    UniqueConstraint('user_id', 'idempotency_key', name='uq_work_feedback_user_request'),
    UniqueConstraint('user_id', 'suggestion_id', 'version', name='uq_work_feedback_user_version'),
)
Index('ix_work_feedback_user_suggestion', work_suggestion_feedback.c.user_id, work_suggestion_feedback.c.suggestion_id)


class FeedbackConflict(ValueError):
    pass


def _record(row):
    if row is None:
        return None
    result = dict(row)
    for key in ('created_at', 'snooze_until'):
        if result[key] is not None and result[key].tzinfo is None:
            result[key] = result[key].replace(tzinfo=UTC)
    return result


class SuggestionFeedbackRepository:
    def __init__(self, engine):
        self.engine = engine

    def receipt(self, user_id: str, receipt_id: str) -> dict | None:
        with self.engine.connect() as connection:
            return _record(connection.execute(select(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id, work_suggestion_feedback.c.id == receipt_id,
            )).mappings().one_or_none())

    def history(self, user_id: str, *, offset: int = 0, limit: int = 20) -> dict:
        if not 0 <= offset <= 2000 or not 1 <= limit <= 50:
            raise ValueError('Feedback history window is out of bounds.')
        with self.engine.connect() as connection:
            rows = connection.execute(select(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id).order_by(
                    work_suggestion_feedback.c.created_at.desc(), work_suggestion_feedback.c.version.desc(), work_suggestion_feedback.c.id,
                ).offset(offset).limit(limit)).mappings().all()
            total = connection.execute(select(func.count()).select_from(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id)).scalar_one()
            legacy = connection.execute(select(action_suggestion_decisions).where(
                action_suggestion_decisions.c.dismissed_by == user_id).order_by(
                    action_suggestion_decisions.c.dismissed_at.desc()).limit(20)).mappings().all()
            items = []
            for row in rows:
                record = _record(row)
                latest = self._latest(connection, user_id, record['suggestion_id'])
                items.append({key: record[key] for key in ('id', 'suggestion_id', 'account_id', 'version', 'reason', 'note', 'created_at', 'snooze_until', 'source_revision')} | {
                    'can_undo': latest['id'] == record['id'] and record['reason'] != 'UNDO',
                    'identity_state': 'CANONICAL_STABLE_ID' if record['suggestion_id'].startswith('suggestion-v2-') else 'RETIRED_UNSTABLE_ID_NOT_REAPPLIED',
                })
        return {'items': items, 'total': total, 'next_offset': offset + limit if offset + limit < total else None,
                'legacy_dismissals': [{'suggestion_id': row['suggestion_id'], 'dismissed_at': row['dismissed_at'],
                                       'state': 'RETIRED_UNSTABLE_ID_NOT_REAPPLIED'} for row in legacy],
                'legacy_limit': 20, 'scope': 'CURRENT_USER_ONLY'}

    @staticmethod
    def _latest(connection, user_id, suggestion_id):
        return _record(connection.execute(select(work_suggestion_feedback).where(
            work_suggestion_feedback.c.user_id == user_id,
            work_suggestion_feedback.c.suggestion_id == suggestion_id,
        ).order_by(work_suggestion_feedback.c.version.desc()).limit(1)).mappings().one_or_none())

    def current(self, user_id: str, suggestion_ids: tuple[str, ...], *, now: datetime,
                source_revisions: dict[str, str] | None = None) -> dict[str, dict]:
        if len(suggestion_ids) > 500:
            raise ValueError('Feedback scope exceeds the bounded suggestion window.')
        result = {}
        with self.engine.connect() as connection:
            rows = connection.execute(select(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id,
                work_suggestion_feedback.c.suggestion_id.in_(suggestion_ids),
            ).order_by(work_suggestion_feedback.c.version.desc())).mappings()
            for row in rows:
                record = _record(row)
                key = record['suggestion_id']
                if key in result:
                    continue
                hidden = record['reason'] in {'WRONG_ACCOUNT', 'ALREADY_DONE', 'NOT_RELEVANT'} or (
                    record['reason'] == 'SNOOZE' and record['snooze_until'] > now)
                source_changed = source_revisions is not None and record['source_revision'] != source_revisions.get(key)
                if source_changed:
                    hidden = False
                result[key] = {'id': record['id'], 'reason': record['reason'], 'note': record['note'],
                               'version': record['version'], 'hidden': hidden, 'snooze_until': record['snooze_until'],
                               'source_revision': record['source_revision'], 'source_changed': source_changed,
                               'created_at': record['created_at'], 'scope': 'CURRENT_USER_ONLY',
                               'authority': 'USER_REPORTED_NOT_VERIFIED; canonical identity, scores and task status are unchanged.'}
        return result

    def append(self, *, user_id: str, suggestion_id: str, account_id: str, reason: str,
               note: str, now: datetime, idempotency_key: str, expected_feedback_id: str | None,
               snooze_until: datetime | None = None, source_revision: str | None = None,
               current_source_revision: str | None = None) -> dict:
        if reason not in {'WRONG_ACCOUNT', 'SNOOZE', 'ALREADY_DONE', 'NOT_RELEVANT', 'UNDO'}:
            raise ValueError('Unsupported feedback reason.')
        if now.tzinfo is None or not 8 <= len(idempotency_key) <= 64 or len(note) > 500:
            raise ValueError('Feedback needs a real aware clock and bounded request fields.')
        if reason in {'WRONG_ACCOUNT', 'ALREADY_DONE'} and not note.strip():
            raise ValueError('Describe the correction or the declared completion source.')
        if reason == 'SNOOZE':
            if snooze_until is None or snooze_until.tzinfo is None:
                raise ValueError('Snooze must end in the next 90 days.')
        elif snooze_until is not None:
            raise ValueError('Only snooze feedback can change timing.')
        request_values = [suggestion_id, account_id, reason, note.strip(),
                          snooze_until.isoformat() if snooze_until else None, expected_feedback_id]
        # Preserve old receipt hashes for history/undo and legacy request replay.
        # New source-aware writes bind the reviewed evidence to the request key.
        if source_revision is not None:
            request_values.append(source_revision)
        fingerprint = sha256(json.dumps(request_values, sort_keys=True).encode()).hexdigest()
        with self.engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                lock = int.from_bytes(sha256(('work-feedback:' + user_id).encode()).digest()[:8], signed=True)
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
            replay = connection.execute(select(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id,
                work_suggestion_feedback.c.idempotency_key == idempotency_key)).mappings().one_or_none()
            if replay:
                if replay['request_hash'] != fingerprint:
                    raise FeedbackConflict('This request key already belongs to different feedback.')
                return _record(replay)
            if source_revision is not None and source_revision != current_source_revision:
                raise FeedbackConflict('Recommendation evidence changed; refresh and review before saving new feedback. Your draft is retained.')
            if reason == 'SNOOZE' and not now < snooze_until <= now + timedelta(days=90):
                raise ValueError('Snooze must end in the next 90 days.')
            latest = self._latest(connection, user_id, suggestion_id)
            if expected_feedback_id != (latest['id'] if latest else None):
                raise FeedbackConflict('Feedback changed; refresh before editing or undoing it.')
            if reason == 'UNDO':
                legacy = connection.execute(select(action_suggestion_decisions.c.suggestion_id).where(
                    action_suggestion_decisions.c.suggestion_id == suggestion_id,
                    action_suggestion_decisions.c.dismissed_by == user_id)).scalar_one_or_none()
                if latest and latest['reason'] == 'UNDO' or not latest and not legacy:
                    raise FeedbackConflict('No active feedback is available to undo.')
            count = connection.execute(select(func.count()).select_from(work_suggestion_feedback).where(
                work_suggestion_feedback.c.user_id == user_id)).scalar_one()
            # Reserve undo capacity: once ordinary writes stop, each remaining
            # active suggestion can still be restored without deleting its audit.
            if count >= 1000 and reason != 'UNDO':
                raise FeedbackConflict('The bounded POC feedback audit limit has been reached; contact the operator.')
            record = {'id': str(uuid4()), 'user_id': user_id, 'suggestion_id': suggestion_id, 'account_id': account_id,
                      'version': latest['version'] + 1 if latest else 1, 'reason': reason, 'note': note.strip(),
                      'created_at': now, 'snooze_until': snooze_until, 'previous_feedback_id': latest['id'] if latest else None,
                      'idempotency_key': idempotency_key, 'request_hash': fingerprint, 'source_revision': source_revision}
            connection.execute(insert(work_suggestion_feedback).values(**record))
            return record
