"""Principal-private, expiring Omni preferences; not a source of commercial facts."""
import json
import re
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
    delete,
    func,
    insert,
    select,
    text,
    update,
)

from btx_omni.persistence.models import metadata

omni_user_memory = Table(
    "omni_user_memory", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(128), nullable=False),
    Column("account_id", String(64)),
    Column("kind", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
Index("ix_omni_memory_user_expiry", omni_user_memory.c.user_id, omni_user_memory.c.expires_at)

# Minimal create receipts survive deletion solely to prevent an old request from
# resurrecting a preference. No preference text or response snapshot is retained.
omni_memory_create_requests = Table(
    'omni_memory_create_requests', metadata,
    Column('user_id', String(128), primary_key=True),
    Column('key_hash', String(64), primary_key=True),
    Column('request_hash', String(64), nullable=False),
    Column('memory_id', String(36), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
)


class MemoryConflict(ValueError):
    pass


class OmniMemoryRepository:
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _lock(connection, user_id):
        if connection.dialect.name == 'postgresql':
            lock = int.from_bytes(sha256(user_id.encode()).digest()[:8], signed=True)
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})

    @staticmethod
    def _record(row):
        value = dict(row)
        for key in ("created_at", "updated_at", "expires_at"):
            if value[key].tzinfo is None:
                value[key] = value[key].replace(tzinfo=UTC)
        return value

    def list(self, user_id: str, *, now: datetime, account_id: str | None = None, for_context: bool = False) -> list[dict]:
        statement = select(omni_user_memory).where(omni_user_memory.c.user_id == user_id)
        if for_context:
            statement = statement.where(omni_user_memory.c.expires_at > now,
                                        (omni_user_memory.c.account_id.is_(None)) | (omni_user_memory.c.account_id == account_id))
        with self.engine.connect() as connection:
            rows = connection.execute(statement.order_by(omni_user_memory.c.updated_at.desc(), omni_user_memory.c.id).limit(25)).mappings().all()
        return [{**self._record(row), "expired": self._record(row)["expires_at"] <= now} for row in rows]

    def save(self, *, user_id: str, account_id: str | None, kind: str, content: str,
             ttl_days: int, now: datetime, memory_id: str | None = None, expected_version: int | None = None,
             idempotency_key: str | None = None) -> dict:
        if kind not in {"ANSWER_STYLE", "WORK_PREFERENCE"} or not 1 <= len(content.strip()) <= 600 or not 1 <= ttl_days <= 365:
            raise ValueError("Invalid bounded memory preference.")
        if now.tzinfo is None:
            raise ValueError("Memory expiry requires an aware real clock.")
        if idempotency_key is not None and (memory_id or not re.fullmatch(r'[A-Za-z0-9._-]{8,64}', idempotency_key)):
            raise ValueError('A bounded create request key cannot be used for an edit.')
        key_hash = sha256(idempotency_key.encode()).hexdigest() if idempotency_key else None
        fingerprint = sha256(json.dumps([account_id, kind, content.strip(), ttl_days]).encode()).hexdigest()
        with self.engine.begin() as connection:
            self._lock(connection, user_id)
            if key_hash:
                replay = connection.execute(select(omni_memory_create_requests).where(
                    omni_memory_create_requests.c.user_id == user_id, omni_memory_create_requests.c.key_hash == key_hash,
                )).mappings().one_or_none()
                if replay:
                    if replay['request_hash'] != fingerprint:
                        raise MemoryConflict('This save request already belongs to different preference content.')
                    existing = connection.execute(select(omni_user_memory).where(
                        omni_user_memory.c.user_id == user_id, omni_user_memory.c.id == replay['memory_id'],
                    )).mappings().one_or_none()
                    if existing is None:
                        raise MemoryConflict('This preference was deleted; retrying its original request will not recreate it.')
                    # Return current state after subsequent edits, without reapplying
                    # old content or renewing expiry. The UI inspects this state.
                    return {**self._record(existing), 'create_replayed': True}
                count = connection.execute(select(func.count()).select_from(omni_memory_create_requests).where(
                    omni_memory_create_requests.c.user_id == user_id)).scalar_one()
                if count >= 1000:
                    raise MemoryConflict('The bounded POC preference-create receipt limit is reached; contact the operator.')
            values = {"account_id": account_id, "kind": kind, "content": content.strip(),
                      "updated_at": now, "expires_at": now + timedelta(days=ttl_days)}
            if memory_id:
                if expected_version is None:
                    raise MemoryConflict("An inspected version is required.")
                result = connection.execute(update(omni_user_memory).where(
                    omni_user_memory.c.id == memory_id, omni_user_memory.c.user_id == user_id,
                    omni_user_memory.c.version == expected_version,
                ).values(**values, version=expected_version + 1))
                if result.rowcount != 1:
                    raise MemoryConflict("Memory is unavailable or changed; refresh your memories.")
            else:
                ids = connection.execute(select(omni_user_memory.c.id).where(omni_user_memory.c.user_id == user_id)).all()
                if len(ids) >= 25:
                    raise MemoryConflict("Delete an unused or expired preference before adding another (limit 25).")
                memory_id = str(uuid4())
                connection.execute(insert(omni_user_memory).values(id=memory_id, user_id=user_id, created_at=now, version=1, **values))
                if key_hash:
                    connection.execute(insert(omni_memory_create_requests).values(
                        user_id=user_id, key_hash=key_hash, request_hash=fingerprint, memory_id=memory_id, created_at=now))
            row = connection.execute(select(omni_user_memory).where(omni_user_memory.c.id == memory_id, omni_user_memory.c.user_id == user_id)).mappings().one()
        return self._record(row)

    def delete(self, memory_id: str, *, user_id: str, expected_version: int) -> None:
        with self.engine.begin() as connection:
            self._lock(connection, user_id)
            result = connection.execute(delete(omni_user_memory).where(
                omni_user_memory.c.id == memory_id, omni_user_memory.c.user_id == user_id,
                omni_user_memory.c.version == expected_version,
            ))
            if result.rowcount != 1:
                raise MemoryConflict("Memory is unavailable or changed; refresh your memories.")
