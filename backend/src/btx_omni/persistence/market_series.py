"""Public-only market vintages over the existing database; immutable revisions.

No account/customer fields enter this owner. A current pointer changes only after
the complete bounded adapter payload validates; failed refresh keeps prior data.
"""
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    insert,
    select,
    text,
    update,
)

from btx_omni.modules.markets.g17 import ADAPTER_VERSION
from btx_omni.modules.markets.registry import BY_ID
from btx_omni.persistence.models import metadata

market_series_vintages = Table(
    'market_series_vintages', metadata,
    Column('id', String(64), primary_key=True),
    Column('series_id', String(64), nullable=False),
    Column('retrieved_at', DateTime(timezone=True), nullable=False),
    Column('release_date', String(10)),
    Column('payload', Text, nullable=False),
)
Index('ix_market_vintage_series_time', market_series_vintages.c.series_id, market_series_vintages.c.retrieved_at)
market_series_current = Table(
    'market_series_current', metadata,
    Column('series_id', String(64), primary_key=True),
    Column('vintage_id', String(64), ForeignKey('market_series_vintages.id'), nullable=False),
    Column('last_verified_at', DateTime(timezone=True), nullable=False),
)
market_refresh_runs = Table(
    'market_refresh_runs', metadata,
    Column('id', String(36), primary_key=True),
    Column('completed_at', DateTime(timezone=True), nullable=False),
    Column('status', String(32), nullable=False),
    Column('report', Text, nullable=False),
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class MarketSeriesRepository:
    def __init__(self, engine):
        self.engine = engine

    def store(self, parsed: dict, *, retrieved_at: datetime, source_url: str,
              http_last_modified: str | None = None, retrieval_kind: str = 'PROVIDED_SOURCE_NOT_LIVE_FETCH') -> dict:
        if retrieval_kind not in {'PROVIDED_SOURCE_NOT_LIVE_FETCH', 'LIVE_PUBLIC_DOWNLOAD', 'CI_HISTORICAL_PUBLIC_EXCERPT'}:
            raise ValueError('Unsupported market retrieval provenance.')
        if retrieved_at.tzinfo is None or parsed.get('adapter_version') != ADAPTER_VERSION:
            raise ValueError('Market import requires an aware clock and supported adapter.')
        series = parsed['series']
        if len(series) != len(BY_ID) or {item['metadata']['id'] for item in series} != set(BY_ID):
            raise ValueError('Market import requires the complete reviewed series set.')
        for item in series:
            if item['metadata'] != BY_ID[item['metadata']['id']].metadata():
                raise ValueError('Market metadata differs from the reviewed registry.')
        run_id = str(uuid4())
        report = {'id': run_id, 'status': 'SUCCEEDED', 'source_url': source_url,
                  'retrieval_kind': retrieval_kind,
                  'retrieved_at': retrieved_at.isoformat(), 'source_sha256': parsed['source_sha256'],
                  'http_last_modified_not_release_date': http_last_modified,
                  'release_date': None, 'release_date_status': 'NOT_EXTRACTED_FROM_PUBLISHED_RELEASE',
                  'created_vintages': 0, 'replayed_series': 0, 'series': []}
        with self.engine.begin() as connection:
            if self.engine.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('btx-public-market-refresh'))"))
            for item in series:
                series_id = item['metadata']['id']
                # Line numbers and changing HTML/whole-file bytes are provenance,
                # not new values. Shared source copies cannot manufacture a revision.
                semantic = {**item, 'observations': [
                    {key: row[key] for key in ('period', 'value', 'status')} for row in item['observations']
                ], 'adapter_version': ADAPTER_VERSION}
                vintage_id = sha256(_json(semantic).encode()).hexdigest()
                current = connection.execute(select(market_series_current).where(
                    market_series_current.c.series_id == series_id)).mappings().one_or_none()
                if current and _aware(current['last_verified_at']) > retrieved_at:
                    raise ValueError('Stale market refresh cannot replace a newer verified snapshot.')
                exists = connection.execute(select(market_series_vintages.c.id).where(
                    market_series_vintages.c.id == vintage_id)).scalar_one_or_none()
                if not exists:
                    payload = {**item, 'adapter_version': ADAPTER_VERSION,
                               'retrieval_kind': retrieval_kind,
                               'source_url': source_url, 'source_sha256': parsed['source_sha256'],
                               'http_last_modified_not_release_date': http_last_modified}
                    connection.execute(insert(market_series_vintages).values(
                        id=vintage_id, series_id=series_id, retrieved_at=retrieved_at,
                        release_date=None, payload=_json(payload)))
                    report['created_vintages'] += 1
                else:
                    report['replayed_series'] += 1
                values = {'vintage_id': vintage_id, 'last_verified_at': retrieved_at}
                if current:
                    connection.execute(update(market_series_current).where(
                        market_series_current.c.series_id == series_id).values(**values))
                else:
                    connection.execute(insert(market_series_current).values(series_id=series_id, **values))
                report['series'].append({'series_id': series_id, 'vintage_id': vintage_id,
                                         'observations': len(item['observations'])})
            connection.execute(insert(market_refresh_runs).values(
                id=run_id, completed_at=retrieved_at, status='SUCCEEDED', report=_json(report)))
        return report

    def failed(self, *, completed_at: datetime, reason: str) -> dict:
        # Only controlled error codes, not arbitrary provider messages/URLs/secrets.
        if reason not in {'SOURCE_UNAVAILABLE', 'SOURCE_CONTRACT_CHANGED', 'REFRESH_DEADLINE'}:
            raise ValueError('Unsupported public market failure code.')
        report = {'id': str(uuid4()), 'status': 'FAILED', 'reason': reason,
                  'prior_data_retained': True, 'completed_at': completed_at.isoformat()}
        with self.engine.begin() as connection:
            connection.execute(insert(market_refresh_runs).values(
                id=report['id'], completed_at=completed_at, status='FAILED', report=_json(report)))
        return report

    def snapshot(self, series_id: str, *, vintage_id: str | None = None) -> dict | None:
        if series_id not in BY_ID:
            raise ValueError('Unknown market series.')
        with self.engine.connect() as connection:
            current = connection.execute(select(market_series_current).where(
                market_series_current.c.series_id == series_id)).mappings().one_or_none()
            selected = vintage_id or (current['vintage_id'] if current else None)
            if selected is None:
                return None
            row = connection.execute(select(market_series_vintages).where(
                market_series_vintages.c.id == selected,
                market_series_vintages.c.series_id == series_id)).mappings().one_or_none()
            if row is None:
                return None
            is_current = bool(current and current['vintage_id'] == selected)
            return {**json.loads(row['payload']), 'vintage_id': row['id'], 'is_current': is_current,
                    'retrieved_at': _aware(row['retrieved_at']).isoformat(), 'release_date': row['release_date'],
                    'last_verified_at': _aware(current['last_verified_at']).isoformat() if is_current else None}

    def vintages(self, series_id: str) -> list[dict]:
        if series_id not in BY_ID:
            raise ValueError('Unknown market series.')
        with self.engine.connect() as connection:
            rows = connection.execute(select(market_series_vintages.c.id, market_series_vintages.c.retrieved_at).where(
                market_series_vintages.c.series_id == series_id).order_by(
                    market_series_vintages.c.retrieved_at.desc(), market_series_vintages.c.id).limit(24)).mappings()
            return [{'vintage_id': row['id'], 'retrieved_at': _aware(row['retrieved_at']).isoformat()} for row in rows]

    def health(self) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(select(market_refresh_runs.c.report).order_by(
                market_refresh_runs.c.completed_at.desc(), market_refresh_runs.c.id).limit(1)).scalar_one_or_none()
        return {'last_run': json.loads(row) if row else None,
                'schedule_status': 'NOT_YET_CONFIGURED', 'vintage_list_limit': 24}
