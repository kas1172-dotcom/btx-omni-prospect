"""Governed, tenant-scoped professional-network import; dry-run by default."""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine, and_, delete, func, insert, or_, select, update

from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.modules.relationships.network_classifier import classify_title
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.persistence import models
from btx_omni.persistence.database import create_database_engine
from btx_omni.providers.sample.environment import build_sample_environment

SOURCE_KIND = "linkedin_connections_csv"
TIE_SOURCE = "linkedin_connection_export"
WORKTREE = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class NormalizedConnectionRecord:
    full_name: str
    company: str
    position: str | None
    connected_on: date | None
    profile_url: str | None


class ConnectionAdapter(Protocol):
    source_kind: str
    def records(self, path: Path) -> tuple[NormalizedConnectionRecord, ...]: ...


class LinkedInConnectionsCsvAdapter:
    source_kind = SOURCE_KIND
    required_headers = frozenset(("First Name", "Last Name", "Company", "Position", "Connected On"))

    def records(self, path: Path) -> tuple[NormalizedConnectionRecord, ...]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not self.required_headers <= set(reader.fieldnames):
                raise ValueError("LinkedIn Connections.csv headers are incomplete")
            output = []
            for row in reader:
                full_name = " ".join(filter(None, (row.get("First Name", "").strip(), row.get("Last Name", "").strip())))
                company = row.get("Company", "").strip()
                if not full_name or not company:
                    continue
                raw_connected = row.get("Connected On", "").strip()
                connected = None
                for fmt in ("%d %b %Y", "%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        connected = datetime.strptime(raw_connected, fmt).replace(tzinfo=UTC).date() if raw_connected else None
                        break
                    except ValueError:
                        continue
                output.append(NormalizedConnectionRecord(full_name, company, row.get("Position", "").strip() or None,
                                                         connected, row.get("URL", "").strip() or None))
            return tuple(output)


def _id(prefix: str, *parts: str) -> str:
    return prefix + ":" + hashlib.sha256("\0".join(parts).encode()).hexdigest()[:40]


def _outside_worktree(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if resolved == WORKTREE or WORKTREE in resolved.parents:
        raise ValueError("Import files inside the git worktree are refused")
    if not resolved.is_file():
        raise ValueError("Import path must be a file")
    return resolved


class NetworkImportRepository:
    def __init__(self, engine: Engine, profiles: tuple[AccountWatchProfile, ...]):
        # SQLAlchemy diagnostics must not serialize imported personal parameters.
        engine.hide_parameters = True
        self.engine, self.profiles = engine, profiles

    def import_file(self, path: Path, *, tenant_id: str, owner_user_id: str, owner_name: str, exported_at: datetime,
                    adapter: ConnectionAdapter | None = None, apply: bool = False) -> dict[str, object]:
        if not owner_user_id.strip() or owner_user_id.strip() == "shared-access":
            raise ValueError("A unique server-configured owner is required")
        source = adapter or LinkedInConnectionsCsvAdapter()
        safe_path = _outside_worktree(path)
        digest = hashlib.sha256(safe_path.read_bytes()).hexdigest()
        rows = source.records(safe_path)
        batch_id = _id("network-batch", tenant_id, source.source_kind, digest)
        owner_id = _id("network-person", tenant_id, batch_id, "owner")
        resolutions = [(row, resolve_entity(row.company, self.profiles), classify_title(row.position)) for row in rows]
        resolved_count = sum(item.canonical_account_id is not None for _, item, _ in resolutions)
        report = {"batch_id": batch_id, "status": "IMPORTED" if apply else "DRY_RUN", "input_rows": len(rows),
                  "imported_rows": len(rows), "resolved_rows": resolved_count, "unresolved_rows": len(rows) - resolved_count,
                  "file_sha256": digest, "data_mode": "IMPORTED", "synthetic": False}
        if not apply:
            return report
        now = datetime.now(UTC)
        unresolved = Counter(row.company for row, resolution, _ in resolutions if resolution.canonical_account_id is None)
        with self.engine.begin() as connection:
            existing = connection.execute(select(models.network_import_batches).where(
                models.network_import_batches.c.tenant_id == tenant_id,
                models.network_import_batches.c.source_kind == source.source_kind,
                models.network_import_batches.c.file_sha256 == digest,
            )).mappings().first()
            if existing:
                if existing["owner_user_id"] != owner_user_id:
                    raise ValueError("File already belongs to another owner; ownership cannot be reassigned")
                return {**report, "status": "UNCHANGED"}
            connection.execute(insert(models.network_import_batches).values(
                id=batch_id, tenant_id=tenant_id, source_kind=source.source_kind, file_sha256=digest,
                exported_at=exported_at, imported_at=now, owner_person_id=owner_id, status="IMPORTED",
                input_row_count=len(rows), imported_row_count=len(rows), resolved_row_count=resolved_count,
                unresolved_row_count=len(rows) - resolved_count, data_mode="IMPORTED",
                visibility="owner_only", owner_user_id=owner_user_id))
            connection.execute(insert(models.network_people).values(
                id=owner_id, tenant_id=tenant_id, kind="internal", display_name=owner_name,
                profile_url=None, batch_id=batch_id))
            for index, (row, resolution, classification) in enumerate(resolutions):
                person_id = _id("network-person", tenant_id, batch_id, str(index), row.full_name, row.profile_url or "")
                connection.execute(insert(models.network_people).values(
                    id=person_id, tenant_id=tenant_id, kind="external", display_name=row.full_name,
                    profile_url=row.profile_url, batch_id=batch_id))
                connection.execute(insert(models.network_affiliations).values(
                    id=_id("network-affiliation", person_id, row.company), tenant_id=tenant_id, person_id=person_id,
                    raw_company_string=row.company, raw_title=row.position, account_id=resolution.canonical_account_id,
                    resolution_method=resolution.method, resolution_state=resolution.state.value,
                    role_family=classification.role_family, seniority_tier=classification.seniority_tier,
                    as_of=exported_at, evidence_state="INFERRED", data_mode="IMPORTED", synthetic=False))
                connection.execute(insert(models.network_ties).values(
                    id=_id("network-tie", owner_id, person_id), tenant_id=tenant_id, internal_person_id=owner_id,
                    external_person_id=person_id,
                    connected_on=datetime.combine(row.connected_on, datetime.min.time(), UTC) if row.connected_on else None,
                    batch_id=batch_id, tie_source=TIE_SOURCE, evidence_state="INFERRED", data_mode="IMPORTED", synthetic=False))
            for company, count in unresolved.items():
                fingerprint = hashlib.sha256(company.casefold().strip().encode()).hexdigest()
                resolution = resolve_entity(company, self.profiles)
                connection.execute(insert(models.network_unresolved_companies).values(
                    id=_id("network-unresolved", tenant_id, batch_id, fingerprint), tenant_id=tenant_id, batch_id=batch_id,
                    company_fingerprint=fingerprint, raw_company_string=company, resolution_state=resolution.state.value,
                    resolution_method=resolution.method, source="network_import", occurrence_count=count))
        return report

    def visible_rows(self, principal: Principal) -> tuple[dict[str, object], ...]:
        if principal.tenant_id is None or principal.role not in {PrincipalRole.SALESPERSON, PrincipalRole.MANAGER}:
            return ()
        permitted = and_(
            models.network_import_batches.c.tenant_id == principal.tenant_id,
            or_(models.network_import_batches.c.visibility == "tenant_shared",
                and_(principal.user_id != "shared-access",
                     models.network_import_batches.c.owner_user_id == principal.user_id)),
        )
        owners = models.network_people.alias("network_owners")
        query = (select(
                    models.network_import_batches.c.id.label("batch_id"),
                    models.network_import_batches.c.exported_at,
                    models.network_import_batches.c.owner_person_id,
                    owners.c.display_name.label("owner_display_name"),
                    models.network_people.c.id.label("person_id"),
                    models.network_people.c.kind.label("person_kind"),
                    models.network_people.c.display_name,
                    models.network_people.c.profile_url,
                    models.network_affiliations.c.raw_company_string,
                    models.network_affiliations.c.raw_title,
                    models.network_affiliations.c.account_id,
                    models.network_affiliations.c.resolution_method,
                    models.network_affiliations.c.role_family,
                    models.network_affiliations.c.seniority_tier,
                    models.network_affiliations.c.as_of,
                    models.network_ties.c.internal_person_id,
                    models.network_ties.c.connected_on,
                    models.network_ties.c.tie_source,
                 )
                 .join(models.network_people, models.network_people.c.batch_id == models.network_import_batches.c.id)
                 .join(owners, owners.c.id == models.network_import_batches.c.owner_person_id)
                 .join(models.network_affiliations, models.network_affiliations.c.person_id == models.network_people.c.id)
                 .join(models.network_ties, models.network_ties.c.external_person_id == models.network_people.c.id)
                 .where(permitted,
                        models.network_import_batches.c.data_mode == "IMPORTED",
                        models.network_people.c.tenant_id == principal.tenant_id,
                        owners.c.tenant_id == principal.tenant_id,
                        owners.c.batch_id == models.network_import_batches.c.id,
                        owners.c.kind == "internal", models.network_people.c.kind == "external",
                        models.network_affiliations.c.tenant_id == principal.tenant_id,
                        models.network_ties.c.tenant_id == principal.tenant_id,
                        models.network_ties.c.batch_id == models.network_import_batches.c.id,
                        models.network_ties.c.internal_person_id == owners.c.id,
                        models.network_affiliations.c.data_mode == "IMPORTED",
                        models.network_ties.c.data_mode == "IMPORTED",
                        models.network_ties.c.synthetic.is_(False),
                        models.network_affiliations.c.synthetic.is_(False)))
        with self.engine.connect() as connection:
            return tuple(dict(row) for row in connection.execute(query).mappings())

    def share_batch(self, batch_id: str, *, tenant_id: str, owner_user_id: str) -> bool:
        if owner_user_id.strip() == "shared-access":
            return False
        with self.engine.begin() as connection:
            result = connection.execute(update(models.network_import_batches).where(
                models.network_import_batches.c.id == batch_id,
                models.network_import_batches.c.tenant_id == tenant_id,
                models.network_import_batches.c.owner_user_id == owner_user_id,
                models.network_import_batches.c.visibility == "owner_only",
            ).values(visibility="tenant_shared"))
            return result.rowcount == 1

    def purge_batch(self, batch_id: str, *, tenant_id: str, apply: bool = False) -> dict[str, object]:
        with self.engine.begin() as connection:
            batch = connection.execute(select(models.network_import_batches.c.id).where(
                models.network_import_batches.c.id == batch_id,
                models.network_import_batches.c.tenant_id == tenant_id,
            ).with_for_update()).first()
            if batch is None:
                return {"status": "NOT_FOUND", "batches": 0, "people": 0, "affiliations": 0, "ties": 0, "review_queue": 0}
            counts = {
                "batches": int(batch is not None),
                "people": connection.scalar(select(func.count()).select_from(models.network_people).where(models.network_people.c.batch_id == batch_id)) or 0,
                "affiliations": connection.scalar(select(func.count()).select_from(models.network_affiliations).join(
                    models.network_people, models.network_people.c.id == models.network_affiliations.c.person_id
                ).where(models.network_people.c.batch_id == batch_id)) or 0,
                "ties": connection.scalar(select(func.count()).select_from(models.network_ties).where(models.network_ties.c.batch_id == batch_id)) or 0,
                "review_queue": connection.scalar(select(func.count()).select_from(models.network_unresolved_companies).where(
                    models.network_unresolved_companies.c.batch_id == batch_id)) or 0,
            }
            report = {"status": "PURGED" if apply else "DRY_RUN", **counts}
            if not apply:
                return report
            person_ids = select(models.network_people.c.id).where(models.network_people.c.batch_id == batch_id)
            connection.execute(delete(models.network_affiliations).where(models.network_affiliations.c.person_id.in_(person_ids)))
            connection.execute(delete(models.network_ties).where(models.network_ties.c.batch_id == batch_id))
            connection.execute(delete(models.network_unresolved_companies).where(models.network_unresolved_companies.c.batch_id == batch_id))
            connection.execute(delete(models.network_people).where(models.network_people.c.batch_id == batch_id))
            connection.execute(delete(models.network_import_batches).where(
                models.network_import_batches.c.id == batch_id,
                models.network_import_batches.c.tenant_id == tenant_id,
            ))
        return report

    def unresolved_company_report(self, *, tenant_id: str) -> tuple[dict[str, object], ...]:
        query = (select(models.network_unresolved_companies.c.raw_company_string.label("company"),
                        func.sum(models.network_unresolved_companies.c.occurrence_count).label("contact_count"))
                 .where(models.network_unresolved_companies.c.tenant_id == tenant_id)
                 .group_by(models.network_unresolved_companies.c.raw_company_string)
                 .order_by(func.sum(models.network_unresolved_companies.c.occurrence_count).desc(),
                           models.network_unresolved_companies.c.raw_company_string))
        with self.engine.connect() as connection:
            return tuple(dict(row) for row in connection.execute(query).mappings())


def main() -> int:
    parser = argparse.ArgumentParser(description="Governed professional-network import operations")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-linkedin")
    importer.add_argument("path", type=Path); importer.add_argument("--tenant-id", required=True)
    importer.add_argument("--owner-name", required=True); importer.add_argument("--owner-user-id", required=True)
    importer.add_argument("--exported-at", required=True); importer.add_argument("--apply", action="store_true")
    purge = commands.add_parser("purge")
    purge.add_argument("batch_id"); purge.add_argument("--tenant-id", required=True); purge.add_argument("--apply", action="store_true")
    unresolved = commands.add_parser("report-unresolved")
    unresolved.add_argument("--tenant-id", required=True)
    args = parser.parse_args()
    environment = build_sample_environment()
    repository = NetworkImportRepository(create_database_engine(Settings()), environment.watch_profiles)
    if args.command == "purge":
        print("network purge:", repository.purge_batch(args.batch_id, tenant_id=args.tenant_id, apply=args.apply))
    elif args.command == "report-unresolved":
        for row in repository.unresolved_company_report(tenant_id=args.tenant_id):
            print(f"{row['company']}\t{row['contact_count']}")
    else:
        report = repository.import_file(args.path, tenant_id=args.tenant_id, owner_user_id=args.owner_user_id,
                                        owner_name=args.owner_name, exported_at=datetime.fromisoformat(args.exported_at), apply=args.apply)
        print("network import:", {key: value for key, value in report.items() if key not in {"batch_id", "file_sha256"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
