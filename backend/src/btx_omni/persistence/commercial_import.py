"""Atomic, ownership-checked commercial import into existing canonical SQL owners."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, and_, insert, select, update

from btx_omni.modules.commercial.crm_mapping import retained_crm_mapping
from btx_omni.modules.commercial.ledger import KEYS, validate_commercial_account
from btx_omni.persistence import models
from btx_omni.persistence.commercial_schema import (
    COLLECTION_TABLES,
    LIFECYCLE_TABLES,
    commercial_account_profiles,
    commercial_import_ownership,
    commercial_import_runs,
)
from btx_omni.providers.sample.environment import SampleEnvironment

PACKAGE_KEY = "btx-omni-commercial-v2"
ORDER_METADATA = "_import_record_order"


def record_key(collection: str) -> str:
    return KEYS.get(collection) or {"contacts": "contact_id", "supply_relationships": "relationship_id"}[collection]


BU_CROSSWALK = {
    "BU-ERA": "era-industries", "BU-GENELMEC": "gen-el-mec",
    "BU-I3D": "i3d-mfg", "BU-APM": "addison-precision",
    "BU-A1J": "a1j-technologies", "BU-CHANDLER": "chandler-industries",
    "BU-HTS": "high-tech-solutions", "BU-MAITLAND": "maitland-engineering",
}


def encoded(value: Any) -> str:
    def serialize(item):
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError(f"Unsupported persisted value: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=serialize)


def digest(value: Any) -> str:
    return sha256(encoded(value).encode()).hexdigest()


def stored_projection(existing, fields):
    """Match imported UTC instants despite database session-zone presentation."""
    result = {key: existing[key] for key in fields}
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC))
    return result


class CommercialImportRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def import_package(
        self, package: dict, crosswalk: dict[str, str], environment: SampleEnvironment,
        *, apply: bool = False, data_mode: str = "SAMPLE", expected_revision: str | None = None,
    ) -> dict:
        if data_mode != "SAMPLE" or package.get("data_mode") != "SIMULATED_ENVIRONMENT":
            raise ValueError("Commercial scenario import requires the SAMPLE environment")
        canonical = {a.id: a for a in environment.accounts}
        source_ids = [a["account_id"] for a in package["accounts"]]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate source account")
        if not set(source_ids) <= crosswalk.keys():
            raise ValueError("Every source account requires an explicit canonical crosswalk")
        targets = [crosswalk[i] for i in source_ids]
        if len(targets) != len(set(targets)) or not set(targets) <= canonical.keys():
            raise ValueError("Crosswalk duplicates or invents canonical account identity")
        if not set(BU_CROSSWALK.values()) <= {u.id for u in environment.business_units}:
            raise ValueError("BTX business-unit crosswalk no longer matches the catalog")
        for account in package["accounts"]:
            if ORDER_METADATA in account:
                raise ValueError("Reserved importer metadata must not be supplied as account data")
            validate_commercial_account(account)
            current = canonical[crosswalk[account["account_id"]]]
            domains = account["identity"]["legacy_identity"]["official_domains"]
            if current.domain not in domains:
                raise ValueError(f"Account domain mismatch for {current.id}")

        now = datetime.now(UTC)
        report: dict[str, Any] = {
            "run_id": str(uuid4()), "applied": apply, "created": 0, "updated": 0,
            "unchanged": 0, "accounts": targets, "removed": 0,
            "package_hash": digest(package), "collections": {},
            "source_package_reference": {k: v for k, v in package.items() if k != 'accounts'},
            "account_source_versions": {crosswalk[a['account_id']]: digest(a) for a in package['accounts']},
        }
        with self.engine.connect() as connection:
            transaction = connection.begin()
            try:
                # Serialize concurrent imports on PostgreSQL, including dry-run
                # reads. SQLite tests use a single writer transaction.
                if connection.dialect.name == "postgresql":
                    from sqlalchemy import text
                    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                    connection.execute(text("SET LOCAL statement_timeout = '30s'"))
                    connection.execute(text("SELECT pg_advisory_xact_lock(72411022)"))
                elif connection.dialect.name == 'sqlite':
                    connection.exec_driver_sql('BEGIN IMMEDIATE')

                prior_rows = connection.execute(select(commercial_account_profiles.c.account_id,
                                                       commercial_account_profiles.c.source_version).where(
                    commercial_account_profiles.c.source_system == PACKAGE_KEY))
                report['prior_revision'] = digest(sorted(tuple(row) for row in prior_rows))
                if expected_revision is not None and report['prior_revision'] != expected_revision:
                    raise ValueError('Commercial records changed after review; repeat the dry-run before applying.')

                def write(table, row, *, shared=False):
                    rid = row["id"]
                    existing = connection.execute(select(table).where(table.c.id == rid).with_for_update()).mappings().first()
                    key = and_(commercial_import_ownership.c.table_name == table.name, commercial_import_ownership.c.record_id == rid)
                    ownership = connection.execute(select(commercial_import_ownership).where(key)).mappings().first()
                    if existing and shared:
                        # Canonical identity may predate this package. Do not
                        # claim ownership or overwrite another source's fields.
                        if table is models.accounts and existing["domain"] != row["domain"]:
                            raise ValueError(f"Persisted canonical identity conflict: {rid}")
                        report["unchanged"] += 1
                        return
                    if existing and (not ownership or ownership["package_key"] != PACKAGE_KEY):
                        raise ValueError(f"Unowned record collision: {table.name}/{rid}")
                    if ownership and not existing:
                        raise ValueError(f"Owned record missing; explicit restoration review required: {table.name}/{rid}")
                    if existing and ownership:
                        # Compare the last imported field projection with actual
                        # storage before replay OR correction. Source hashes alone
                        # cannot prove that an independent edit has not occurred.
                        stored = stored_projection(existing, row)
                        if digest(stored) != ownership['source_hash']:
                            raise ValueError(f"Owned record changed outside this import; reconcile before applying: {table.name}/{rid}")
                    if existing:
                        for scope_key in ("account_id", "program_id", "commercial_context_id"):
                            if table is models.commercial_quotes and scope_key == "program_id":
                                # Quote program is a derived index over its
                                # governed lines, not the quote's identity.
                                continue
                            if scope_key in row and existing[scope_key] != row[scope_key]:
                                raise ValueError(f"Record scope cannot be reassigned: {table.name}/{rid}")
                    content_hash = digest(row)
                    if ownership and ownership["source_hash"] == content_hash:
                        report["unchanged"] += 1
                        return
                    if existing:
                        connection.execute(update(table).where(table.c.id == rid).values(**row))
                        report["updated"] += 1
                    else:
                        connection.execute(insert(table).values(**row))
                        report["created"] += 1
                    owner = {"table_name": table.name, "record_id": rid, "package_key": PACKAGE_KEY, "source_hash": content_hash, "updated_at": now}
                    if ownership:
                        connection.execute(update(commercial_import_ownership).where(key).values(**owner))
                    else:
                        connection.execute(insert(commercial_import_ownership).values(**owner))

                for account in package["accounts"]:
                    aid = crosswalk[account["account_id"]]
                    current = canonical[aid]
                    write(models.accounts, {"id": aid, "name": current.legal_name, "domain": current.domain, "relationship": current.relationship.value}, shared=True)
                    base = {k: v for k, v in account.items() if k not in COLLECTION_TABLES}
                    base[ORDER_METADATA] = {collection: [r[record_key(collection)] for r in account[collection]] for collection in COLLECTION_TABLES}
                    write(commercial_account_profiles, {"id": aid, "account_id": aid, "payload": encoded(base), "source_system": PACKAGE_KEY, "source_record_id": account["account_id"], "source_version": digest(account)})
                    truth = {"source_system": PACKAGE_KEY, "evidence_state": "CONFIRMED", "data_mode": "SAMPLE", "synthetic": True}
                    def tr(rid, truth=truth):
                        return {**truth, "source_record_id": rid}
                    context_id = f"commercial:{aid}:account"
                    write(models.commercial_contexts, {"id": context_id, "account_id": aid, "business_unit_id": "ALL_BUSINESS_UNITS", "currency": account["currency"], "ttm_revenue_minor": account["ttm_summary"]["revenue_minor"], "ttm_bookings_minor": account["ttm_summary"]["bookings_minor"], "payload": encoded({"scope": "ACCOUNT_AGGREGATE", "as_of": account["as_of"], "ttm_summary": account["ttm_summary"]}), **tr(context_id)})
                    paperless_id, crm_id = f"paperless:{aid}", f"crm:{aid}"
                    write(models.paperless_accounts, {"id": paperless_id, "account_id": aid, "name": current.legal_name, **tr(paperless_id)})
                    crm_owner, crm_mapping = retained_crm_mapping(environment.crm_companies, aid)
                    write(models.crm_companies, {"id": crm_id, "account_id": aid, "owner_id": crm_owner, "payload": encoded(crm_mapping), **tr(crm_id)})
                    components = {r["component_id"]: r for r in account["components"]}
                    revisions = {r["quote_revision_id"]: r for r in account["quote_revisions"]}
                    quote_lines = {r["quote_line_id"]: r for r in account["quote_lines"]}
                    order_lines = {r["order_line_id"]: r for r in account["order_lines"]}
                    for collection, table in COLLECTION_TABLES.items():
                        rows = account[collection]
                        key = record_key(collection)
                        if collection == "components":
                            scope = table.c.program_id.in_(select(models.programs.c.id).where(models.programs.c.account_id == aid))
                        elif collection == "monthly_commercial_history":
                            scope = table.c.commercial_context_id == context_id
                        else:
                            scope = table.c.account_id == aid
                        previous_ids = set(connection.execute(select(table.c.id).where(
                            scope, table.c.source_system == PACKAGE_KEY,
                        )).scalars())
                        omitted = previous_ids - {record[key] for record in rows}
                        if omitted:
                            raise ValueError(f"Explicit retraction required for omitted {collection} records: {sorted(omitted)}")
                        report["collections"][collection] = report["collections"].get(collection, 0) + len(rows)
                        for record in rows:
                            rid = record[key]
                            common = {"id": rid, "account_id": aid}
                            if collection in LIFECYCLE_TABLES:
                                row = {**common, "payload": encoded(record), "source_system": PACKAGE_KEY, "source_record_id": rid, "source_version": digest(record)}
                            elif collection == "programs":
                                row = {**common, "name": record["name"], "system": None, "source_payload": encoded(record), **tr(rid)}
                            elif collection == "components":
                                row = {"id": rid, "program_id": record["program_id"], "name": record["name"], "industry": None, "business_unit_ids": encoded([BU_CROSSWALK[record["business_unit_id"]]]), "source_payload": encoded(record), **tr(rid)}
                            elif collection == "quotes":
                                rev = revisions[record["current_revision_id"]]
                                scoped_components = [components[quote_lines[lid]["component_id"]] for lid in rev["line_ids"]]
                                unit_ids = {BU_CROSSWALK[c["business_unit_id"]] for c in scoped_components}
                                program_ids = {c["program_id"] for c in scoped_components}
                                row = {**common, "paperless_account_id": paperless_id, "business_unit_id": next(iter(unit_ids)) if len(unit_ids) == 1 else "MULTIPLE_BUSINESS_UNITS", "program_id": next(iter(program_ids)) if len(program_ids) == 1 else None, "status": record["status"], "quoted_at": rev["issued_date"], "value_minor": rev["total_minor"], "currency": account["currency"], "payload": encoded(record), **tr(rid)}
                            elif collection == "orders":
                                line = order_lines[record["line_ids"][0]]
                                row = {**common, "quote_id": record["quote_id"], "business_unit_id": BU_CROSSWALK[line["business_unit_id"]], "component_class_id": line["component_id"], "program_id": line["program_id"], "status": record["status"], "promised_date": line["committed_date"], "actual_ship_date": None, "amount_minor": record["total_minor"], "payload": encoded(record), **tr(rid)}
                            elif collection == "interactions":
                                row = {**common, "company_id": crm_id, "occurred_at": datetime.fromisoformat(record["date"]).replace(tzinfo=UTC), "payload": encoded(record), **tr(rid)}
                            elif collection == "opportunities":
                                row = {**common, "company_id": crm_id, "program_id": record["program_id"], "business_unit_id": BU_CROSSWALK[components[record["component_id"]]["business_unit_id"]], "payload": encoded(record), **tr(rid)}
                            elif collection == "monthly_commercial_history":
                                row = {"id": rid, "commercial_context_id": context_id, "month": record["period"], "revenue_minor": record["revenue_minor"], "bookings_minor": record["bookings_minor"], "source_payload": encoded(record), **tr(rid)}
                            else:
                                raise ValueError(f"Unmapped collection: {collection}")
                            write(table, row)
                if apply:
                    connection.execute(insert(commercial_import_runs).values(id=report["run_id"], package_key=PACKAGE_KEY, manifest_hash=report["package_hash"], as_of=package["commercial_as_of"], report=encoded(report), completed_at=now))
                    transaction.commit()
                else:
                    transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
        return report

    def accounts(self) -> dict[str, dict]:
        """Reconstruct the source-shaped record from its sole persisted owners."""
        return self.snapshot()[1]

    @staticmethod
    def _crm_mappings(connection):
        return {row['account_id']: {'id': row['id'], 'owner_id': row['owner_id'], 'properties': json.loads(row['payload'])}
                for row in connection.execute(select(models.crm_companies).where(models.crm_companies.c.source_system == PACKAGE_KEY)).mappings()}

    def crm_mappings(self):
        with self.engine.connect() as connection:
            return self._crm_mappings(connection)

    def source_package(self, account_id: str, source_version: str) -> dict:
        """Bounded audit lookup; never label the deployed file as imported evidence."""
        with self.engine.connect() as connection:
            rows = connection.execute(select(commercial_import_runs).where(
                commercial_import_runs.c.package_key == PACKAGE_KEY,
            ).order_by(commercial_import_runs.c.completed_at.desc(), commercial_import_runs.c.id).limit(100)).mappings()
            for row in rows:
                report = json.loads(row['report'])
                if report.get('account_source_versions', {}).get(account_id) != source_version:
                    continue
                return {'availability': 'MATCHED_PERSISTED_IMPORT', 'import_run_id': row['id'],
                        'package_semantic_sha256': row['manifest_hash'], 'account_source_version': source_version,
                        'imported_at': row['completed_at'], 'source_metadata': report['source_package_reference'],
                        'hash_basis': 'Canonical JSON semantic SHA-256; original bundle byte hashes remain in input coverage.'}
        return {'availability': 'NO_MATCHING_IMPORT_METADATA_IN_BOUNDED_AUDIT', 'account_source_version': source_version,
                'source_metadata': None, 'search_limit': 100,
                'limitation': 'Older imports may predate retained package metadata. The runtime file is not proof of the imported source.'}

    def revision(self) -> str:
        with self.engine.connect() as connection:
            rows = connection.execute(select(
                commercial_account_profiles.c.account_id,
                commercial_account_profiles.c.source_version,
            ).where(commercial_account_profiles.c.source_system == PACKAGE_KEY))
            return digest(sorted(tuple(row) for row in rows))

    def snapshot(self, *, include_crm=False):
        """Read one consistent revision, including when an import commits mid-read."""
        with self.engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
            profiles = list(connection.execute(select(commercial_account_profiles).where(
                commercial_account_profiles.c.source_system == PACKAGE_KEY
            )).mappings())
            revision = digest(sorted((row["account_id"], row["source_version"]) for row in profiles))
            result = {row["account_id"]: json.loads(row["payload"]) for row in profiles}
            record_orders = {aid: profile.pop(ORDER_METADATA, {}) for aid, profile in result.items()}
            for collection, table in COLLECTION_TABLES.items():
                for profile in result.values():
                    profile[collection] = []
                field = "source_payload" if "source_payload" in table.c else "payload"
                rows = connection.execute(select(table).where(table.c.source_system == PACKAGE_KEY)).mappings()
                for row in rows:
                    if collection == "components":
                        aid = next((aid for aid, p in result.items() if any(pr["program_id"] == row["program_id"] for pr in p["programs"])), None)
                    elif collection == "monthly_commercial_history":
                        aid = row["commercial_context_id"].removeprefix("commercial:").removesuffix(":account")
                    else:
                        aid = row["account_id"]
                    if aid in result:
                        result[aid][collection].append(json.loads(row[field]))
                for aid, profile in result.items():
                    expected = record_orders[aid].get(collection)
                    if expected is not None:
                        key = record_key(collection)
                        by_id = {record[key]: record for record in profile[collection]}
                        if set(by_id) != set(expected) or len(by_id) != len(expected):
                            raise ValueError("Persisted collection membership disagrees with its source-order manifest")
                        profile[collection] = [by_id[rid] for rid in expected]
            return (revision, result, self._crm_mappings(connection)) if include_crm else (revision, result)
