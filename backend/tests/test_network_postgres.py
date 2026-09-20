"""Opt-in verification against an already migrated disposable localhost database."""
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, delete, func, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError
from test_network_import import csv_file

from btx_omni.persistence import models
from btx_omni.persistence.network_import import NetworkImportRepository
from btx_omni.persistence.seed_network_sample import assert_local_database


def test_real_postgres_import_constraints_and_purge(tmp_path):
    url = os.environ.get("NETWORK_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("DB-dependent: requires disposable local NETWORK_TEST_POSTGRES_URL")
    assert_local_database(url)
    engine = create_engine(url, hide_parameters=True)
    inspector = inspect(engine)
    expected = {"network_import_batches", "network_people", "network_affiliations",
                "network_ties", "network_unresolved_companies"}
    assert expected <= set(inspector.get_table_names())
    checks = {item["name"] for item in inspector.get_check_constraints("network_import_batches")}
    assert {"ck_network_batch_imported", "ck_network_batch_visibility"} <= checks
    assert inspector.get_indexes("network_affiliations")
    repository = NetworkImportRepository(engine, ())
    batch = repository.import_file(csv_file(tmp_path), tenant_id="postgres-test", owner_user_id="test-owner",
                                   owner_name="Fake Owner", exported_at=datetime(2026, 9, 1, tzinfo=UTC), apply=True)
    batch_id = str(batch["batch_id"])
    try:
        for change in ({"data_mode": "SAMPLE"}, {"visibility": "public"}):
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(update(models.network_import_batches).where(
                    models.network_import_batches.c.id == batch_id).values(**change))
        for table in (models.network_affiliations, models.network_ties):
            for change in ({"data_mode": "SAMPLE"}, {"synthetic": True}):
                with pytest.raises(IntegrityError), engine.begin() as connection:
                    connection.execute(update(table).where(table.c.tenant_id == "postgres-test").values(**change))
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(insert(models.network_people).values(id="invalid-kind", tenant_id="postgres-test",
                batch_id=batch_id, kind="unknown", display_name="Fake"))
        with engine.connect() as connection:
            assert connection.scalar(select(models.network_import_batches.c.data_mode).where(
                models.network_import_batches.c.id == batch_id)) == "IMPORTED"
    finally:
        repository.purge_batch(batch_id, tenant_id="postgres-test", apply=True)
    with engine.connect() as connection:
        for table in (models.network_import_batches, models.network_people, models.network_affiliations,
                      models.network_ties, models.network_unresolved_companies):
            assert not connection.execute(select(table).where(table.c.tenant_id == "postgres-test")).first()
    engine.dispose()


def test_local_seed_imports_exactly_200_and_is_idempotent(monkeypatch, capsys):
    import btx_omni.persistence.seed_network_sample as seed
    from btx_omni.core.config import Settings

    url = os.environ.get("NETWORK_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("DB-dependent: requires disposable local NETWORK_TEST_POSTGRES_URL")
    assert_local_database(url)
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        if connection.scalar(select(func.count()).select_from(models.accounts)):
            pytest.skip("Seed integration test requires an empty disposable account catalog")
        connection.execute(insert(models.accounts), [
            {"id": "honeywell", "name": "Honeywell", "relationship": "PROSPECT"},
            {"id": "boeing", "name": "Boeing", "relationship": "PROSPECT"},
        ])
    monkeypatch.setattr(seed, "Settings", lambda: Settings(_env_file=None, database_url=url))
    monkeypatch.setattr("sys.argv", ["seed", "--tenant-id", "seed-test", "--owner-user-id", "seller-1", "--apply"])
    repo = NetworkImportRepository(engine, ())
    try:
        assert seed.main() == 0
        assert seed.main() == 0
        with engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(models.network_people).where(
                models.network_people.c.tenant_id == "seed-test", models.network_people.c.kind == "external")) == 200
            assert connection.scalar(select(func.count()).select_from(models.network_ties).where(
                models.network_ties.c.tenant_id == "seed-test")) == 200
        output = capsys.readouterr().out
        assert "UNCHANGED" in output
        assert "Fake Contact" not in output and "example.invalid" not in output
    finally:
        with engine.connect() as connection:
            batch_ids = list(connection.scalars(select(models.network_import_batches.c.id).where(
                models.network_import_batches.c.tenant_id == "seed-test")))
        for batch_id in batch_ids:
            repo.purge_batch(batch_id, tenant_id="seed-test", apply=True)
        with engine.begin() as connection:
            connection.execute(delete(models.accounts).where(models.accounts.c.id.in_(("honeywell", "boeing"))))
        engine.dispose()
