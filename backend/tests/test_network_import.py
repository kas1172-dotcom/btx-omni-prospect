from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select

from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.persistence import models
from btx_omni.persistence.network_import import (
    WORKTREE,
    LinkedInConnectionsCsvAdapter,
    NetworkImportRepository,
)

CSV = """First Name,Last Name,URL,Email Address,Company,Position,Connected On
Ada,Example,https://example.invalid/ada,ignored@example.invalid,Acme Corporation,Director of Procurement,01 Sep 2026
Lin,Example,https://example.invalid/lin,ignored2@example.invalid,Unknown Works,Engineer,2026-08-01
"""


def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "Connections.csv"
    path.write_text(CSV, encoding="utf-8")
    return path


def test_linkedin_adapter_ignores_email_and_normalizes_fake_rows(tmp_path):
    rows = LinkedInConnectionsCsvAdapter().records(csv_file(tmp_path))
    assert len(rows) == 2
    assert rows[0].company == "Acme Corporation"
    assert not hasattr(rows[0], "email")


def test_import_is_dry_run_by_default_and_masks_report(tmp_path):
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    profiles = (AccountWatchProfile("acme", "Acme Corporation"),)
    report = NetworkImportRepository(engine, profiles).import_file(csv_file(tmp_path), tenant_id="tenant-a", owner_user_id="seller-1", owner_name="Owner Example", exported_at=datetime(2026, 9, 1, tzinfo=UTC))
    assert report["status"] == "DRY_RUN"
    assert report["resolved_rows"] == 1
    with engine.connect() as connection:
        assert connection.execute(select(models.network_import_batches)).first() is None


def test_apply_is_idempotent_and_never_persists_email(tmp_path):
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(models.accounts).values(id="acme", name="Acme", relationship="PROSPECT", domain=None))
    repo = NetworkImportRepository(engine, (AccountWatchProfile("acme", "Acme Corporation"),))
    args = {"tenant_id": "tenant-a", "owner_user_id": "seller-1", "owner_name": "Owner Example", "exported_at": datetime(2026, 9, 1, tzinfo=UTC), "apply": True}
    assert repo.import_file(csv_file(tmp_path), **args)["status"] == "IMPORTED"
    assert repo.import_file(csv_file(tmp_path), **args)["status"] == "UNCHANGED"
    with engine.connect() as connection:
        people = connection.execute(select(models.network_people)).mappings().all()
        assert len(people) == 3
        assert "ignored@example.invalid" not in repr(people)
        unresolved = connection.execute(select(models.network_unresolved_companies)).mappings().one()
        assert unresolved["source"] == "network_import" and unresolved["occurrence_count"] == 1


def test_paths_inside_worktree_are_refused():
    with pytest.raises(ValueError, match="worktree"):
        NetworkImportRepository(create_engine("sqlite://"), ()).import_file(
            WORKTREE / "README.md", tenant_id="tenant-a", owner_user_id="seller-1", owner_name="Owner", exported_at=datetime.now(UTC))


def test_purge_is_dry_run_then_removes_every_batch_trace(tmp_path):
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(models.accounts).values(id="acme", name="Acme", relationship="PROSPECT", domain=None))
    repo = NetworkImportRepository(engine, (AccountWatchProfile("acme", "Acme Corporation"),))
    imported = repo.import_file(csv_file(tmp_path), tenant_id="tenant-a", owner_user_id="seller-1",
                                owner_name="Owner Example", exported_at=datetime(2026, 9, 1, tzinfo=UTC), apply=True)
    batch_id = str(imported["batch_id"])
    repo.import_file(csv_file(tmp_path), tenant_id="tenant-b", owner_user_id="seller-2",
                     owner_name="Another Fake Owner", exported_at=datetime(2026, 9, 1, tzinfo=UTC), apply=True)
    assert repo.purge_batch(batch_id, tenant_id="other-tenant", apply=True) == {
        "status": "NOT_FOUND", "batches": 0, "people": 0, "affiliations": 0, "ties": 0, "review_queue": 0}
    preview = repo.purge_batch(batch_id, tenant_id="tenant-a")
    assert preview == {"status": "DRY_RUN", "batches": 1, "people": 3, "affiliations": 2, "ties": 2, "review_queue": 1}
    assert repo.purge_batch(batch_id, tenant_id="tenant-a", apply=True)["status"] == "PURGED"
    with engine.connect() as connection:
        for table in (models.network_import_batches, models.network_people, models.network_affiliations,
                      models.network_ties, models.network_unresolved_companies):
            assert connection.scalar(select(func.count()).select_from(table).where(table.c.tenant_id == "tenant-a")) == 0
            assert connection.scalar(select(func.count()).select_from(table).where(table.c.tenant_id == "tenant-b")) > 0


def test_unresolved_report_contains_company_counts_and_no_personal_fields(tmp_path):
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    repo = NetworkImportRepository(engine, ())
    repo.import_file(csv_file(tmp_path), tenant_id="tenant-a", owner_user_id="seller-1", owner_name="Owner Example",
                     exported_at=datetime(2026, 9, 1, tzinfo=UTC), apply=True)
    report = repo.unresolved_company_report(tenant_id="tenant-a")
    assert report == ({"company": "Acme Corporation", "contact_count": 1},
                      {"company": "Unknown Works", "contact_count": 1})
    assert "Example" not in repr(report) and "invalid" not in repr(report)
