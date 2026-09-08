"""Durable bounded call reservations, without prompts, private reasoning or prices."""
import json
import re
from datetime import UTC, timedelta
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Table,
    Text,
    func,
    insert,
    select,
    text,
    update,
)

from btx_omni.persistence.models import metadata

POLICY_VERSION = 'BTX_AI_CALL_BUDGET_1'
ai_call_receipts = Table('ai_call_receipts', metadata,
    Column('id', String(36), primary_key=True),
    Column('environment_id', String(80), nullable=False),
    Column('actor_id', String(128), nullable=False),
    Column('purpose', String(40), nullable=False),
    Column('provider', String(32), nullable=False),
    Column('model', String(128), nullable=False),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('lease_expires_at', DateTime(timezone=True), nullable=False),
    Column('completed_at', DateTime(timezone=True)),
    Column('status', String(32), nullable=False),
    Column('policy', Text, nullable=False),
    Column('usage', Text),
)
Index('ix_ai_calls_environment_started', ai_call_receipts.c.environment_id, ai_call_receipts.c.started_at)
Index('ix_ai_calls_actor_started', ai_call_receipts.c.environment_id, ai_call_receipts.c.actor_id, ai_call_receipts.c.started_at)
Index('ix_ai_calls_active_lease', ai_call_receipts.c.environment_id, ai_call_receipts.c.status, ai_call_receipts.c.lease_expires_at)


class AiBudgetExceeded(RuntimeError):
    pass


class AiUsageRepository:
    def __init__(self, engine):
        self.engine = engine

    def reserve(self, *, environment_id, actor_id, purpose, model, now, daily_environment_limit=1000,
                daily_actor_limit=400, concurrent_environment_limit=2, concurrent_actor_limit=1, lease_seconds=180):
        if now.tzinfo is None:
            raise ValueError('AI budget accounting requires a real UTC-aware clock.')
        for value, maximum in ((environment_id, 80), (actor_id, 128), (purpose, 40), (model, 128)):
            if not isinstance(value, str) or not 1 <= len(value) <= maximum or re.search(r'[\x00-\x1f]', value):
                raise ValueError('AI reservation identity is invalid.')
        if not 1 <= daily_actor_limit <= daily_environment_limit <= 10000 or not 1 <= concurrent_actor_limit <= concurrent_environment_limit <= 8 or not 30 <= lease_seconds <= 1200:
            raise ValueError('AI budget policy exceeds bounded POC limits.')
        now = now.astimezone(UTC)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        policy = {'version': POLICY_VERSION, 'daily_environment_calls': daily_environment_limit, 'daily_actor_calls': daily_actor_limit,
                  'concurrent_environment_leases': concurrent_environment_limit, 'concurrent_actor_leases': concurrent_actor_limit,
                  'lease_seconds': lease_seconds, 'cost_usd': None, 'budget_basis': 'SDK_CALL_RESERVATIONS_NOT_PROVIDER_BILLING'}
        with self.engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                connection.execute(text("SET LOCAL statement_timeout = '3s'"))
                connection.execute(text('SELECT pg_advisory_xact_lock(72411030)'))
            elif connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            environment = ai_call_receipts.c.environment_id == environment_id
            connection.execute(update(ai_call_receipts).where(environment, ai_call_receipts.c.status == 'RESERVED',
                               ai_call_receipts.c.lease_expires_at <= now).values(status='EXPIRED_OUTCOME_UNKNOWN'))
            daily = select(func.count()).select_from(ai_call_receipts).where(environment,
                ai_call_receipts.c.started_at >= day, ai_call_receipts.c.started_at < day + timedelta(days=1))
            if connection.execute(daily).scalar_one() >= daily_environment_limit:
                raise AiBudgetExceeded('Workspace daily AI call budget reached.')
            if connection.execute(daily.where(ai_call_receipts.c.actor_id == actor_id)).scalar_one() >= daily_actor_limit:
                raise AiBudgetExceeded('Your daily AI call budget was reached.')
            active = select(func.count()).select_from(ai_call_receipts).where(environment, ai_call_receipts.c.status == 'RESERVED', ai_call_receipts.c.lease_expires_at > now)
            if connection.execute(active).scalar_one() >= concurrent_environment_limit:
                raise AiBudgetExceeded('Workspace AI concurrency budget is occupied; retry after the active call finishes.')
            if connection.execute(active.where(ai_call_receipts.c.actor_id == actor_id)).scalar_one() >= concurrent_actor_limit:
                raise AiBudgetExceeded('An AI call is already active for this user; wait for its result.')
            identifier = str(uuid4())
            connection.execute(insert(ai_call_receipts).values(id=identifier, environment_id=environment_id, actor_id=actor_id,
                purpose=purpose, provider='gemini', model=model, started_at=now, lease_expires_at=now + timedelta(seconds=lease_seconds),
                status='RESERVED', policy=json.dumps(policy, sort_keys=True)))
        return identifier

    def complete(self, receipt_id, *, now, status, usage=None):
        if now.tzinfo is None or status not in {'RESPONSE_RECEIVED', 'AUTH_FAILED', 'TIMEOUT', 'PROVIDER_QUOTA', 'FAILED'}:
            raise ValueError('Invalid AI receipt completion.')
        usage = usage or {}
        allowed = {'prompt_tokens', 'output_tokens', 'total_tokens', 'thinking_token_count', 'finish_reason', 'elapsed_ms'}
        if set(usage) - allowed:
            raise ValueError('Only bounded usage metadata belongs in an AI receipt.')
        clean = {}
        for key in allowed:
            value = usage.get(key)
            if key == 'finish_reason':
                clean[key] = value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', value) else None
            elif key == 'elapsed_ms':
                clean[key] = value if type(value) in {int, float} and 0 <= value <= 3600000 else None
            else:
                clean[key] = value if type(value) is int and 0 <= value <= 100000000 else None
        clean['cost_usd'] = None
        with self.engine.begin() as connection:
            if connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            elif connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                connection.execute(text("SET LOCAL statement_timeout = '3s'"))
            statement = select(ai_call_receipts).where(ai_call_receipts.c.id == receipt_id).with_for_update()
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                raise ValueError('AI reservation not found.')
            if row['status'] not in {'RESERVED', 'EXPIRED_OUTCOME_UNKNOWN'}:
                if row['status'] != status or json.loads(row['usage']) != clean:
                    raise ValueError('A completed AI receipt cannot be rewritten.')
                return
            started = row['started_at'].replace(tzinfo=UTC) if row['started_at'].tzinfo is None else row['started_at']
            if now < started:
                raise ValueError('AI completion precedes its reservation.')
            connection.execute(update(ai_call_receipts).where(ai_call_receipts.c.id == receipt_id).values(
                completed_at=now, status=status, usage=json.dumps(clean, sort_keys=True, allow_nan=False)))

    def summary(self, *, environment_id, actor_id, now):
        if now.tzinfo is None:
            raise ValueError('AI accounting requires an aware clock.')
        day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with self.engine.connect() as connection:
            rows = connection.execute(select(ai_call_receipts).where(ai_call_receipts.c.environment_id == environment_id,
                ai_call_receipts.c.started_at >= day, ai_call_receipts.c.started_at < day + timedelta(days=1))).mappings().all()
        own = [row for row in rows if row['actor_id'] == actor_id]
        measured = [json.loads(row['usage']) for row in own if row['usage']]
        known = [usage['total_tokens'] for usage in measured if usage['total_tokens'] is not None]
        return {'policy_version': POLICY_VERSION, 'utc_day': day.date().isoformat(), 'workspace_reserved_calls': len(rows),
                'your_reserved_calls': len(own), 'your_measured_total_tokens': sum(known) if known else None,
                'your_unknown_usage_calls': len(own) - len(known), 'cost_usd': None,
                'basis': 'Call reservations include failures and unknown outcomes. Provider billing and task success are separate.'}
