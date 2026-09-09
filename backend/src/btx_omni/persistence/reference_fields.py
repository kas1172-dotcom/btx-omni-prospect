"""Versioned private workbook references over existing canonical account IDs."""
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
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

reference_field_versions = Table(
    'reference_field_versions', metadata,
    Column('id', String(64), primary_key=True),
    Column('row_key', String(220), nullable=False, index=True),
    # Like the existing work owner, IDs span baseline and durable public account
    # projections. Validate through that canonical service, not only the eleven
    # rows currently owned by the commercial SQL accounts table.
    Column('account_id', String(64), nullable=False, index=True),
    Column('payload', Text, nullable=False),
    Column('imported_at', DateTime(timezone=True), nullable=False),
)
reference_field_current = Table(
    'reference_field_current', metadata,
    Column('row_key', String(220), primary_key=True),
    Column('version_id', ForeignKey('reference_field_versions.id'), nullable=False, unique=True),
)
reference_field_import_runs = Table(
    'reference_field_import_runs', metadata,
    Column('id', String(36), primary_key=True),
    Column('completed_at', DateTime(timezone=True), nullable=False),
    Column('report', Text, nullable=False),
)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return sha256(_encoded(value).encode()).hexdigest()


class ReferenceFieldRepository:
    def __init__(self, engine):
        self.engine = engine

    def import_package(self, package, *, canonical_account_ids, apply=False, expected_revision=None, data_mode='SAMPLE'):
        if data_mode != 'SAMPLE' or package.get('schema_version') != 'BTX_WORKBOOK_REFERENCE_1' or package.get('classification') != 'PRIVATE_USER_PROVIDED_REFERENCE':
            raise ValueError('Private workbook import requires the governed SAMPLE reference schema.')
        rows = package['rows']
        if not 1 <= len(rows) <= 2000 or len({r['row_key'] for r in rows}) != len(rows):
            raise ValueError('Reference rows exceed bounds or duplicate replacement keys.')
        sources = {source['file']: source for source in package['sources']}
        payloads = {}
        for row in rows:
            aid = row['canonical_account_id']
            if aid not in canonical_account_ids:
                raise ValueError('A reference row requires an existing canonical account; no automatic merge is allowed.')
            source = sources.get(row['workbook'])
            if not source or row['workbook_sha256'] != source['sha256'] or not re.fullmatch('[0-9a-f]{64}', source['sha256']):
                raise ValueError('Reference source version is missing or mismatched.')
            if row['row_key'] != f"{row['workbook']}:{row['sheet']}:{row['row_number']}" or len(row['row_key']) > 220:
                raise ValueError('Reference replacement key does not preserve its source coordinate.')
            header = next((h for h in source['headers'] if h['sheet'] == row['sheet']), None)
            if not header or row['row_number'] <= header['row_number']:
                raise ValueError('Reference row is not a data row under its declared header.')
            columns = {re.sub('[0-9]', '', cell): (cell, label) for cell, label in header['values'].items()}
            fields = row['fields']
            if len(fields) != len(columns) or {f['column'] for f in fields} != set(columns):
                raise ValueError('Every source column needs a retained value or explicit null.')
            for field in fields:
                if field.get('group') not in {'company', 'site', 'classification', 'legacy_commercial'}:
                    raise ValueError('Reference field group is not governed.')
                if not isinstance(field.get('label'), str) or not field['label'].strip():
                    raise ValueError('Reference fields require readable labels.')
                if field.get('value') is not None and type(field['value']) not in {str, int, float, bool}:
                    raise ValueError('Reference field values must retain scalar cells.')
                cell, label = columns[field['column']]
                if field['source_header_cell'] != cell or field['source_header'] != label or field['source_cell'] != field['column'] + str(row['row_number']):
                    raise ValueError('Reference field lineage differs from its source column.')
                if field.get('source_formula') and field.get('validation_state') != 'INVALID_PHONE_FORMULA_CACHE':
                    raise ValueError('Source formulas cannot silently become observed values.')
            payloads[row['row_key']] = {**row, 'source_metadata': source,
                'classification': package['classification'], 'authority': package['authority']}
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text('SELECT pg_advisory_xact_lock(72411028)'))
            prior = dict(connection.execute(select(reference_field_current.c.row_key, reference_field_current.c.version_id)).all())
            revision = _digest(sorted(prior.items()))
            if apply and expected_revision is None:
                raise ValueError('Apply requires the inspected reference revision.')
            if expected_revision is not None and revision != expected_revision:
                raise ValueError('Reference fields changed after review; repeat the dry-run.')
            if set(prior) - set(payloads):
                raise ValueError('Omitted source rows cannot authorize deletion.')
            report = {'run_id': str(uuid4()), 'applied': apply, 'prior_revision': revision, 'created': 0, 'updated': 0, 'unchanged': 0,
                'removed': 0, 'canonical_accounts_created': 0, 'row_count': len(rows), 'package_sha256': _digest(package)}
            expected = {}
            for key, payload in sorted(payloads.items()):
                version = _digest(payload)
                expected[key] = version
                state = 'unchanged' if prior.get(key) == version else 'updated' if key in prior else 'created'
                report[state] += 1
                if state == 'updated':
                    previous_account = connection.execute(select(reference_field_versions.c.account_id).where(reference_field_versions.c.id == prior[key])).scalar_one()
                    if previous_account != payload['canonical_account_id']:
                        raise ValueError('Reference account reassignment requires separate reviewed identity correction.')
                if apply and state != 'unchanged':
                    existing = connection.execute(select(reference_field_versions.c.id).where(reference_field_versions.c.id == version)).scalar_one_or_none()
                    if existing is None:
                        connection.execute(insert(reference_field_versions).values(id=version, row_key=key, account_id=payload['canonical_account_id'], payload=_encoded(payload), imported_at=now))
                    if key in prior:
                        connection.execute(update(reference_field_current).where(reference_field_current.c.row_key == key).values(version_id=version))
                    else:
                        connection.execute(insert(reference_field_current).values(row_key=key, version_id=version))
            report['current_revision'] = _digest(sorted(expected.items())) if apply else revision
            report['proposed_revision'] = _digest(sorted(expected.items()))
            if apply:
                connection.execute(insert(reference_field_import_runs).values(id=report['run_id'], completed_at=now, report=_encoded(report)))
            return report

    def list(self, account_id, *, offset=0, limit=3):
        if not 0 <= offset <= 2000 or not 1 <= limit <= 10:
            raise ValueError('Reference pagination is out of bounds.')
        joined = reference_field_current.join(reference_field_versions, reference_field_current.c.version_id == reference_field_versions.c.id)
        with self.engine.connect() as connection:
            total = connection.execute(select(func.count()).select_from(joined).where(reference_field_versions.c.account_id == account_id)).scalar_one()
            records = connection.execute(select(reference_field_versions).select_from(joined).where(
                reference_field_versions.c.account_id == account_id).order_by(reference_field_versions.c.row_key).offset(offset).limit(limit)).mappings().all()
        return {'account_id': account_id, 'items': [{'version_id': row['id'], 'imported_at': row['imported_at'], 'is_current': True, **json.loads(row['payload'])} for row in records],
            'total': total, 'next_offset': offset + limit if offset + limit < total else None,
            'authority': 'Original workbook references; not current financial history, verified location or official scores.'}

    def version(self, account_id, version_id):
        with self.engine.connect() as connection:
            row = connection.execute(select(reference_field_versions).where(reference_field_versions.c.account_id == account_id,
                reference_field_versions.c.id == version_id)).mappings().one_or_none()
            if row is None:
                return None
            current = connection.execute(select(reference_field_current.c.version_id).where(reference_field_current.c.row_key == row['row_key'])).scalar_one_or_none()
        return {'version_id': row['id'], 'is_current': current == row['id'], 'imported_at': row['imported_at'], **json.loads(row['payload'])}
