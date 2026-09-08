import importlib.util
from pathlib import Path
from types import SimpleNamespace

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from btx_omni.core.config import get_settings

BACKEND_ROOT = Path(__file__).parents[1]
REVISION_0009 = "0009_btx_facility_location_metadata"
REVISION_0008 = "0008_commercial_and_edges"
HEAD_REVISION = "0035_account_planning"


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _upgrade(config: Config, revision: str) -> None:
    get_settings.cache_clear()
    command.upgrade(config, revision)


def _downgrade(config: Config, revision: str) -> None:
    get_settings.cache_clear()
    command.downgrade(config, revision)


def _version(database_url: str) -> str:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _revision_module():
    path = BACKEND_ROOT / "alembic" / "versions" / "0009_btx_facility_location_metadata.py"
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self, dialect_name: str) -> None:
        self.dialect_name = dialect_name
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect_name))

    def alter_column(self, *args, **kwargs) -> None:
        self.calls.append(("alter_column", args, kwargs))

    def add_column(self, *args, **kwargs) -> None:
        self.calls.append(("add_column", args, kwargs))


def test_revision_ids_fit_0009_postgresql_version_capacity_and_keep_topology() -> None:
    module = _revision_module()
    script = ScriptDirectory.from_config(_config("sqlite://"))
    revisions = tuple(item.revision for item in script.walk_revisions(base="base", head="heads"))

    assert script.get_heads() == [HEAD_REVISION]
    assert script.get_revision(HEAD_REVISION).down_revision == "0034_seller_itineraries"
    assert script.get_revision("0034_seller_itineraries").down_revision == "0033_monitor_research_journal"
    assert script.get_revision("0033_monitor_research_journal").down_revision == "0032_omni_run_receipts"
    assert script.get_revision("0032_omni_run_receipts").down_revision == "0031_communication_versions"
    assert script.get_revision("0031_communication_versions").down_revision == "0030_ai_call_receipts"
    assert script.get_revision("0030_ai_call_receipts").down_revision == "0029_feedback_source_revision"
    assert script.get_revision("0029_feedback_source_revision").down_revision == "0028_private_reference_fields"
    assert script.get_revision("0028_private_reference_fields").down_revision == "0027_memory_create_receipts"
    assert script.get_revision("0027_memory_create_receipts").down_revision == "0026_market_series"
    assert script.get_revision('0026_market_series').down_revision == '0025_work_feedback'
    assert script.get_revision("0025_work_feedback").down_revision == "0024_monitor_funnel"
    assert script.get_revision("0024_monitor_funnel").down_revision == "0023_omni_private_memory"
    assert script.get_revision("0023_omni_private_memory").down_revision == "0022_commercial_lifecycle"
    assert script.get_revision("0022_commercial_lifecycle").down_revision == "0021_monitor_entity_candidate_resolutions"
    assert script.get_revision(REVISION_0009).down_revision == REVISION_0008
    assert max(map(len, revisions)) <= module.ALEMBIC_VERSION_ID_CAPACITY


def test_0009_widens_only_postgresql_before_its_schema_changes() -> None:
    module = _revision_module()
    postgresql = _FakeOp("postgresql")
    module.op = postgresql
    module.upgrade()

    assert postgresql.calls[0][0] == "alter_column"
    assert postgresql.calls[0][1] == ("alembic_version", "version_num")
    assert postgresql.calls[0][2]["type_"].length == module.ALEMBIC_VERSION_ID_CAPACITY
    assert [call[0] for call in postgresql.calls[1:]] == ["add_column", "add_column", "add_column"]

    sqlite = _FakeOp("sqlite")
    module.op = sqlite
    module.upgrade()
    assert [call[0] for call in sqlite.calls] == ["add_column", "add_column", "add_column"]


def test_sqlite_fresh_base_to_head_uses_the_unchanged_chain(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setenv("BTX_DATABASE_URL", database_url)
    config = _config(database_url)

    _upgrade(config, "head")
    assert _version(database_url) == HEAD_REVISION


def test_sqlite_0008_to_0009_downgrade_and_reupgrade_are_valid(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'cycle.db'}"
    monkeypatch.setenv("BTX_DATABASE_URL", database_url)
    config = _config(database_url)

    _upgrade(config, REVISION_0008)
    assert _version(database_url) == REVISION_0008
    _upgrade(config, REVISION_0009)
    assert _version(database_url) == REVISION_0009
    _downgrade(config, REVISION_0008)
    assert _version(database_url) == REVISION_0008
    _upgrade(config, "head")
    assert _version(database_url) == HEAD_REVISION
