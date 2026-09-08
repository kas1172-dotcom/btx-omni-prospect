"""Resumable public research journal owned by the existing Monitor repository.

Network/model calls must occur between transactions. A fenced lease prevents a
late provider response from completing a step after another worker resumes it.
Only public investigation records belong here, never private seller prompts.
"""
import json
from contextlib import contextmanager
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    insert,
    select,
    text,
    update,
)

from btx_omni.persistence.models import metadata

VERSION = 'BTX_MONITOR_RESEARCH_JOURNAL_1'
runs = Table('monitor_research_runs', metadata,
    Column('id', String(64), primary_key=True),
    Column('event_reference', String(200), nullable=False),
    Column('source_revision', String(64), nullable=False),
    Column('status', String(32), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
    Column('lease_token', String(36)), Column('lease_until', DateTime(timezone=True)),
    Column('completed_steps', Integer, nullable=False),
    Column('attempt_count', Integer, nullable=False),
    Column('result', Text),
)
steps = Table('monitor_research_steps', metadata,
    Column('run_id', ForeignKey('monitor_research_runs.id'), primary_key=True),
    Column('number', Integer, primary_key=True),
    Column('tool', String(80), nullable=False),
    Column('arguments_hash', String(64), nullable=False),
    Column('status', String(32), nullable=False),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('completed_at', DateTime(timezone=True)),
    Column('result', Text),
)


def _time(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json(value, limit=120000):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)
    if len(encoded.encode()) > limit:
        raise ValueError('Public research record exceeds its budget.')
    return encoded


class ResearchLeaseUnavailable(ValueError):
    pass


class ResearchBudgetExhausted(ValueError):
    pass


class MonitorResearchJournal:
    """Persistence helper attached to MonitorRepository, not another Monitor."""

    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def _transaction(self):
        with self.engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            elif connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            yield connection

    def acquire(self, *, event_reference, source_revision, configuration, now,
                lease_seconds=90, max_attempts=3):
        if (now.tzinfo is None or not 1 <= lease_seconds <= 300 or not 1 <= max_attempts <= 3
                or not 1 <= len(event_reference) <= 200 or len(source_revision) != 64
                or any(char not in '0123456789abcdef' for char in source_revision)):
            raise ValueError('Invalid public research run bounds.')
        identifier = sha256(_json((VERSION, event_reference, source_revision, configuration), 8000).encode()).hexdigest()
        with self._transaction() as connection:
            dialect = connection.dialect.name
            if dialect == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert as conflict_insert
            elif dialect == 'sqlite':
                from sqlalchemy.dialects.sqlite import insert as conflict_insert
            else:
                raise ValueError('Research journal requires a qualified database.')
            connection.execute(conflict_insert(runs).values(id=identifier, event_reference=event_reference,
                source_revision=source_revision, status='PENDING', created_at=now, updated_at=now,
                completed_steps=0, attempt_count=0).on_conflict_do_nothing(index_elements=['id']))
            row = connection.execute(select(runs).where(runs.c.id == identifier).with_for_update()).mappings().one()
            if row['status'] == 'COMPLETED':
                return identifier, None
            if row['lease_until'] and _time(row['lease_until']) > now:
                raise ResearchLeaseUnavailable('An active research worker owns this run.')
            if row['attempt_count'] >= max_attempts:
                raise ResearchLeaseUnavailable('Research attempt budget exhausted; inspect recorded failures.')
            if row['status'] == 'PAUSED':
                retry_at = _time(row['updated_at']) + timedelta(seconds=min(300, 60 * 2 ** (row['attempt_count'] - 1)))
                if now < retry_at:
                    raise ResearchLeaseUnavailable(f'Research retry cooldown until {retry_at.isoformat()}.')
            # A crash may leave an admitted call with unknown provider outcome.
            # Keep that attempt; a resumed read uses a new step number.
            connection.execute(update(steps).where(steps.c.run_id == identifier, steps.c.status == 'STARTED')
                               .values(status='INTERRUPTED_UNKNOWN', completed_at=now))
            token = str(uuid4())
            connection.execute(update(runs).where(runs.c.id == identifier).values(status='RUNNING',
                lease_token=token, lease_until=now + timedelta(seconds=lease_seconds), updated_at=now,
                attempt_count=row['attempt_count'] + 1))
        return identifier, token

    def _owned(self, connection, identifier, token, now):
        row = connection.execute(select(runs).where(runs.c.id == identifier).with_for_update()).mappings().one_or_none()
        if (row is None or row['status'] != 'RUNNING' or not token or row['lease_token'] != token
                or row['lease_until'] is None or _time(row['lease_until']) <= now):
            raise ResearchLeaseUnavailable('Research lease expired or was superseded.')
        return row

    def start_step(self, identifier, token, *, tool, arguments, now, max_steps=12):
        if not tool or len(tool) > 80 or not 1 <= max_steps <= 12 or now.tzinfo is None:
            raise ValueError('Invalid research step bounds.')
        arguments_hash = sha256(_json(arguments, 8000).encode()).hexdigest()
        with self._transaction() as connection:
            self._owned(connection, identifier, token, now)
            rows = connection.execute(select(steps.c.number, steps.c.status).where(steps.c.run_id == identifier)).all()
            if any(row.status == 'STARTED' for row in rows):
                raise ValueError('Complete the admitted step before starting another.')
            if len(rows) >= max_steps:
                raise ResearchBudgetExhausted('Research step budget exhausted.')
            number = max((row.number for row in rows), default=0) + 1
            connection.execute(insert(steps).values(run_id=identifier, number=number, tool=tool,
                arguments_hash=arguments_hash, status='STARTED', started_at=now))
        return number

    def complete_step(self, identifier, token, number, *, result, now, failed=False):
        encoded = _json(result)
        if now.tzinfo is None:
            raise ValueError('An aware completion clock is required.')
        with self._transaction() as connection:
            self._owned(connection, identifier, token, now)
            scope = (steps.c.run_id == identifier, steps.c.number == number)
            row = connection.execute(select(steps).where(*scope)).mappings().one_or_none()
            if row is None or now < _time(row['started_at']):
                raise ValueError('Unknown step or invalid completion chronology.')
            state = 'FAILED' if failed else 'COMPLETED'
            if row['status'] != 'STARTED':
                if row['status'] == state and row['result'] == encoded:
                    return
                raise ValueError('A completed step is immutable.')
            connection.execute(update(steps).where(*scope).values(status=state, completed_at=now, result=encoded))
            connection.execute(update(runs).where(runs.c.id == identifier).values(updated_at=now,
                completed_steps=runs.c.completed_steps + (0 if failed else 1)))

    def finish(self, identifier, token, *, result, now, complete):
        if now.tzinfo is None:
            raise ValueError('An aware completion clock is required.')
        encoded = _json(result, 160000)
        with self._transaction() as connection:
            self._owned(connection, identifier, token, now)
            pending = connection.execute(select(steps.c.number).where(steps.c.run_id == identifier,
                steps.c.status == 'STARTED')).first()
            if pending:
                raise ValueError('Cannot finish while a research call has unknown outcome.')
            connection.execute(update(runs).where(runs.c.id == identifier).values(
                status='COMPLETED' if complete else 'PAUSED', result=encoded,
                updated_at=now, lease_token=None, lease_until=None))

    def get(self, identifier):
        with self.engine.connect() as connection:
            row = connection.execute(select(runs).where(runs.c.id == identifier)).mappings().one_or_none()
            if row is None:
                return None
            records = connection.execute(select(steps).where(steps.c.run_id == identifier).order_by(steps.c.number)).mappings().all()
        result = {key: value for key, value in row.items() if key not in {'lease_token', 'lease_until'}}
        result['result'] = json.loads(row['result']) if row['result'] else None
        result['steps'] = [{**dict(item), 'result': json.loads(item['result']) if item['result'] else None} for item in records]
        result['contract_version'] = VERSION
        return result

    def latest_for_source(self, event_reference, source_revision):
        """Only the exact current source assertion can supply investigation context."""
        with self.engine.connect() as connection:
            identifier = connection.execute(select(runs.c.id).where(
                runs.c.event_reference == event_reference, runs.c.source_revision == source_revision,
                runs.c.status.in_(('COMPLETED', 'PAUSED')),
            ).order_by(runs.c.updated_at.desc(), runs.c.id).limit(1)).scalar_one_or_none()
        return self.get(identifier) if identifier else None
