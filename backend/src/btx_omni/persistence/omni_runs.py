"""Private request receipts: canonical steps and final output, never chain-of-thought."""
import json
import re
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Table,
    Text,
    insert,
    select,
    text,
    update,
)

from btx_omni.persistence.models import metadata

VERSION = 'BTX_OMNI_RUN_AUDIT_1'
omni_runs = Table('omni_runs', metadata,
    Column('id', String(36), primary_key=True),
    Column('actor_id', String(128), nullable=False),
    Column('request_hash', String(64), nullable=False),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('completed_at', DateTime(timezone=True)),
    Column('status', String(32), nullable=False),
    Column('result_hash', String(64)),
    Column('result', Text),
)
Index('ix_omni_runs_actor_started', omni_runs.c.actor_id, omni_runs.c.started_at)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


class OmniRunRepository:
    def __init__(self, engine):
        self.engine = engine

    def start(self, *, actor_id, request, now):
        if not isinstance(actor_id, str) or not 1 <= len(actor_id) <= 128 or re.search(r'[\x00-\x1f]', actor_id) or now.tzinfo is None:
            raise ValueError('Invalid private Omni run identity or clock.')
        encoded = _encoded(request)
        if len(encoded.encode()) > 40000:
            raise ValueError('Omni request audit exceeds its bounded input contract.')
        identifier = str(uuid4())
        with self.engine.begin() as connection:
            connection.execute(insert(omni_runs).values(id=identifier, actor_id=actor_id,
                request_hash=sha256(encoded.encode()).hexdigest(), started_at=now.astimezone(UTC), status='RUNNING'))
        return identifier

    def finish(self, identifier, *, actor_id, result, now, failed=False):
        if now.tzinfo is None:
            raise ValueError('Omni completion requires an aware clock.')
        encoded = _encoded(result)
        if len(encoded.encode()) > 160000:
            raise ValueError('Omni audit output exceeds its bounded record contract.')
        fingerprint = sha256(encoded.encode()).hexdigest()
        status = 'FAILED' if failed else 'ANSWER_RECORDED'
        with self.engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                connection.execute(text("SET LOCAL statement_timeout = '3s'"))
            elif connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            scope = (omni_runs.c.id == identifier, omni_runs.c.actor_id == actor_id)
            existing = connection.execute(select(omni_runs).where(*scope).with_for_update()).mappings().first()
            if not existing:
                raise KeyError('Omni run is unavailable in this user scope.')
            if existing['status'] != 'RUNNING':
                if existing['result_hash'] == fingerprint and existing['status'] == status:
                    return
                raise ValueError('A completed Omni run receipt is immutable.')
            started = existing['started_at']
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if now < started:
                raise ValueError('Completion cannot precede the run start.')
            connection.execute(update(omni_runs).where(*scope).values(status=status, completed_at=now,
                result_hash=fingerprint, result=encoded))

    def get(self, identifier, *, actor_id, now):
        with self.engine.connect() as connection:
            row = connection.execute(select(omni_runs).where(omni_runs.c.id == identifier, omni_runs.c.actor_id == actor_id)).mappings().first()
        if row is None:
            return None
        result = dict(row)
        started = row['started_at'] if row['started_at'].tzinfo else row['started_at'].replace(tzinfo=UTC)
        result['operational_state'] = 'INTERRUPTED_OUTCOME_UNKNOWN' if row['status'] == 'RUNNING' and now - started > timedelta(minutes=5) else row['status']
        result['result'] = json.loads(row['result']) if row['result'] else None
        result['contract_version'] = VERSION
        result['authority'] = 'Run receipt, not proof of task correctness, current evidence, CRM delivery or business approval.'
        result.pop('actor_id')
        return result


def answer_receipt(answer, *, build):
    """Allowlisted completed tool receipts, not raw prompts, model reasoning or memory."""
    reads = answer.structured_reads or {}
    relationship = answer.structured_relationship or {}
    market = answer.structured_market or {}
    return {
        'contract_version': VERSION, 'build': build,
        'account_id': answer.account_id, 'answer': answer.content,
        'recommended_action': answer.recommended_action, 'missingness': answer.missingness,
        'citations': answer.citations, 'provider': answer.language_provider, 'model': answer.language_model,
        'provider_status': answer.provider_status, 'provider_usage': answer.provider_usage,
        'retrieval': {key: reads.get(key) for key in ('configuration_version', 'revision', 'stop_reason', 'steps', 'elapsed_ms', 'max_calls', 'outbound_queries')},
        'graph_revision': relationship.get('graph_revision'), 'market_vintage_id': market.get('vintage_id'),
        'execution': {'external_writes': 0, 'work_writes': 0, 'memory_writes': 0,
                      'scope': 'This read-only Omni request; separate explicitly approved UI workflows are not executed here.'},
        'validation': {key: answer.context_used.get(key) for key in ('synthesis_validation', 'canonical_retrieval_status', 'interpretation_status')},
    }
