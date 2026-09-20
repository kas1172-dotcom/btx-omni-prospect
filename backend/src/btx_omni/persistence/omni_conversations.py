"""Private, actor/tenant-bound chat storage; never business evidence or memory."""
import json
from datetime import timedelta
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
    delete,
    insert,
    select,
    update,
)

from btx_omni.persistence.models import metadata
from btx_omni.persistence.omni_runs import omni_runs

conversations = Table('omni_conversations', metadata,
    Column('id', String(36), primary_key=True), Column('owner_key', String(64), nullable=False),
    Column('title', String(80), nullable=False), Column('turns', Text, nullable=False),
    Column('version', Integer, nullable=False), Column('updated_at', DateTime(timezone=True), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False))
Index('ix_omni_conversations_owner_updated', conversations.c.owner_key, conversations.c.updated_at)
feedback = Table('omni_chat_feedback', metadata,
    Column('id', String(36), primary_key=True), Column('conversation_id', String(36), nullable=False),
    Column('owner_key', String(64), nullable=False), Column('run_id', String(36), nullable=False),
    Column('rating', String(4), nullable=False), Column('reason', String(500), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False))


def owner_key(principal):
    return sha256(json.dumps([principal.tenant_id, principal.user_id]).encode()).hexdigest()


class ConversationRepository:
    def __init__(self, engine, *, retention_days=30):
        self.engine, self.retention_days = engine, retention_days

    def _remove(self, connection, row):
        runs = [turn.get('response', {}).get('run_id') for turn in json.loads(row['turns'])]
        connection.execute(delete(omni_runs).where(omni_runs.c.id.in_([r for r in runs if r])))
        connection.execute(delete(feedback).where(feedback.c.conversation_id == row['id'], feedback.c.owner_key == row['owner_key']))
        connection.execute(delete(conversations).where(conversations.c.id == row['id'], conversations.c.owner_key == row['owner_key']))

    def list(self, principal, now):
        key = owner_key(principal)
        with self.engine.begin() as c:
            expired = c.execute(select(conversations).where(conversations.c.owner_key == key, conversations.c.expires_at <= now)).mappings().all()
            for row in expired:
                self._remove(c, row)
            rows = c.execute(select(conversations.c.id, conversations.c.title, conversations.c.updated_at, conversations.c.version)
                             .where(conversations.c.owner_key == key, conversations.c.expires_at > now)
                             .order_by(conversations.c.updated_at.desc()).limit(50)).mappings().all()
        return [dict(row) for row in rows]

    def get(self, identifier, principal, now):
        with self.engine.connect() as c:
            row = c.execute(select(conversations).where(conversations.c.id == identifier,
                conversations.c.owner_key == owner_key(principal), conversations.c.expires_at > now)).mappings().first()
        if not row:
            raise KeyError('Conversation not found.')
        return {k: json.loads(v) if k == 'turns' else v for k, v in row.items() if k != 'owner_key'}

    def create(self, principal, now):
        identifier = str(uuid4())
        with self.engine.begin() as c:
            c.execute(insert(conversations).values(id=identifier, owner_key=owner_key(principal), title='New conversation',
                turns='[]', version=1, updated_at=now, expires_at=now + timedelta(days=self.retention_days)))
        return self.get(identifier, principal, now)

    def append(self, identifier, principal, now, *, version, turns):
        current = self.get(identifier, principal, now)
        combined = [*current['turns'], *turns]
        if len(combined) > 100 or len(json.dumps(combined, default=str)) > 600000:
            raise ValueError('This conversation is full. Start a new conversation.')
        title = next((t['text'][:80] for t in combined if t['role'] == 'user'), 'New conversation') if current['title'] == 'New conversation' else current['title']
        with self.engine.begin() as c:
            result = c.execute(update(conversations).where(conversations.c.id == identifier,
                conversations.c.owner_key == owner_key(principal), conversations.c.version == version,
                conversations.c.expires_at > now).values(turns=json.dumps(combined, default=str), title=title,
                    version=version + 1, updated_at=now, expires_at=now + timedelta(days=self.retention_days)))
            if result.rowcount != 1:
                raise ValueError('Conversation changed. Reload before retrying.')
        return self.get(identifier, principal, now)

    def rename(self, identifier, principal, now, title):
        if not title.strip() or len(title) > 80:
            raise ValueError('Use a title of at most 80 characters.')
        self.get(identifier, principal, now)
        with self.engine.begin() as c:
            c.execute(update(conversations).where(conversations.c.id == identifier,
                conversations.c.owner_key == owner_key(principal)).values(title=title.strip(), updated_at=now))
        return self.get(identifier, principal, now)

    def delete(self, identifier, principal, now):
        self.get(identifier, principal, now)
        with self.engine.begin() as c:
            row = c.execute(select(conversations).where(conversations.c.id == identifier,
                conversations.c.owner_key == owner_key(principal)).with_for_update()).mappings().first()
            if row:
                self._remove(c, row)

    def rate(self, identifier, principal, now, run_id, rating, reason):
        thread = self.get(identifier, principal, now)
        if rating not in {'up', 'down'} or len(reason) > 500 or not any(t.get('response', {}).get('run_id') == run_id for t in thread['turns']):
            raise ValueError('Feedback must reference an answer in this conversation.')
        identifier_receipt = str(uuid4())
        with self.engine.begin() as c:
            c.execute(insert(feedback).values(id=identifier_receipt, conversation_id=identifier, owner_key=owner_key(principal),
                run_id=run_id, rating=rating, reason=reason, created_at=now))
        return {'id': identifier_receipt, 'business_data_changed': False}
