from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select

from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence import models
from btx_omni.persistence import network_import as module

HEADER = "First Name,Last Name,URL,Company,Position,Connected On\r\n"


def test_official_preamble_bom_crlf_unicode_duplicates_missing_fields(tmp_path):
    path = tmp_path / "fake.csv"
    row = "Faké,Example,https://example.invalid/fake,,,04 Mar 2024\r\n"
    path.write_bytes(("\ufeffNotes:\r\nFake export note\r\n\r\n" + HEADER + row + row +
                      "Other,Fake,,Unresolved Example Works,,odd date\r\n").encode())
    records = module.LinkedInConnectionsCsvAdapter().records(path)
    assert len(records) == 2
    assert records[0].full_name == "Faké Example"
    assert records[0].company == "" and records[0].position is None
    assert str(records[0].connected_on) == "2024-03-04"
    assert records[1].connected_on is None


@pytest.mark.parametrize("contents,reason", [
    ("unexpected,columns\nFake,Example", "headers"),
    (HEADER + "x" * 301 + ",Fake,,Company,Engineer,\n", "length"),
    (HEADER + "Fake,Example\n", "column count"),
])
def test_invalid_files_fail_with_masked_error(tmp_path, contents, reason):
    path = tmp_path / "fake.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match=reason) as error:
        module.LinkedInConnectionsCsvAdapter().records(path)
    assert "Example" not in str(error.value)


def test_size_limit_before_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 100)
    path = tmp_path / "fake.csv"
    path.write_bytes(b"x" * 101)
    with pytest.raises(ValueError, match="limit"):
        module.LinkedInConnectionsCsvAdapter().records(path)


@pytest.mark.parametrize("cell", ["=1+1", "+1", "-1", "@SUM(A1)", "  =1", "\t+1"])
def test_spreadsheet_formula_cells_are_neutralized(cell):
    assert module.spreadsheet_safe(cell) == "'" + cell


def test_newer_snapshot_supersedes_without_inheriting_share_and_purge_is_idempotent(tmp_path):
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    repo = module.NetworkImportRepository(engine, ())
    path = tmp_path / "fake.csv"
    path.write_text(HEADER + "Fake,One,,Unknown Works,Engineer,\n", encoding="utf-8")
    args = dict(tenant_id="fake-tenant", owner_user_id="fake-owner", owner_name="Fake Owner", apply=True)
    old = repo.import_file(path, exported_at=datetime(2026, 1, 1, tzinfo=UTC), **args)
    repo.share_batch(old["batch_id"], tenant_id="fake-tenant", owner_user_id="fake-owner")
    path.write_text(HEADER + "Fake,Two,,Unknown Works,Director,\n", encoding="utf-8")
    new = repo.import_file(path, exported_at=datetime(2026, 2, 1, tzinfo=UTC), **args)
    assert repo.import_file(path, exported_at=datetime(2026, 2, 1, tzinfo=UTC), **args)["status"] == "UNCHANGED"
    owner = Principal("fake-owner", "Fake", PrincipalRole.SALESPERSON, "fake-tenant")
    other = Principal("fake-other", "Fake", PrincipalRole.SALESPERSON, "fake-tenant")
    assert [row["display_name"] for row in repo.visible_rows(owner)] == ["Fake Two"]
    assert repo.visible_rows(other) == ()
    assert repo.unresolved_company_report(tenant_id="fake-tenant") == ({"company": "Unknown Works", "contact_count": 1},)
    with pytest.raises(ValueError, match="another owner"):
        repo.import_file(path, exported_at=datetime(2026, 2, 1, tzinfo=UTC), **{**args, "owner_user_id": "fake-other"})
    path.write_text(HEADER + "Fake,Three,,Unknown Works,Director,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="newer"):
        repo.import_file(path, exported_at=datetime(2026, 1, 1, tzinfo=UTC), **args)
    for batch in (old, new):
        assert repo.purge_batch(batch["batch_id"], tenant_id="fake-tenant", apply=True)["status"] == "PURGED"
        assert repo.purge_batch(batch["batch_id"], tenant_id="fake-tenant", apply=True)["status"] == "NOT_FOUND"
    assert repo.visible_rows(owner) == ()
    assert repo.unresolved_company_report(tenant_id="fake-tenant") == ()
    with engine.connect() as conn:
        for table in (models.network_import_batches, models.network_people, models.network_affiliations,
                      models.network_ties, models.network_unresolved_companies):
            assert conn.scalar(select(func.count()).select_from(table)) == 0


def test_cli_purge_requires_flag_and_typed_confirmation(tmp_path, monkeypatch, capsys):
    from btx_omni.core.config import Settings
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    repo = module.NetworkImportRepository(engine, ())
    path = tmp_path / "fake.csv"
    path.write_text(HEADER + "Fake,One,,Unknown Works,Engineer,\n", encoding="utf-8")
    batch = repo.import_file(path, tenant_id="fake", owner_user_id="unique", owner_name="Fake",
                             exported_at=datetime(2026, 1, 1, tzinfo=UTC), apply=True)["batch_id"]
    monkeypatch.setattr(module, "Settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(module, "create_database_engine", lambda settings: engine)
    base = ["network", "purge", batch, "--tenant-id", "fake"]
    monkeypatch.setattr("sys.argv", base + ["--apply"])
    with pytest.raises(SystemExit):
        module.main()
    monkeypatch.setattr("sys.argv", base)
    assert module.main() == 0
    assert repo.purge_batch(batch, tenant_id="fake")["batches"] == 1
    monkeypatch.setattr("sys.argv", base + ["--apply", "--confirm", batch])
    assert module.main() == 0
    assert repo.purge_batch(batch, tenant_id="fake")["batches"] == 0
    output = capsys.readouterr().out
    assert "PURGED" in output and "Fake" not in output and batch not in output


def test_shared_access_cannot_import_even_dry_run(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        module.NetworkImportRepository(create_engine("sqlite://"), ()).import_file(
            tmp_path / "absent.csv", tenant_id="fake", owner_user_id="shared-access", owner_name="Fake",
            exported_at=datetime(2026, 1, 1, tzinfo=UTC))
