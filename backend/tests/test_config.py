from btx_omni.core.config import Settings
from btx_omni.persistence.database import (
    Base,
    create_database_engine,
    create_session_factory,
)


def test_settings_reads_database_url_from_environment(monkeypatch) -> None:
    database_url = "postgresql+psycopg://test_user:test_password@db:5432/test_db"
    monkeypatch.setenv("BTX_DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


def test_database_factory_uses_settings_url_without_connecting() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test_user:test_password@db:5432/test_db",
    )

    engine = create_database_engine(settings)
    session_factory = create_session_factory(settings)

    assert engine.url.username == "test_user"
    assert engine.url.password == "test_password"
    assert engine.url.host == "db"
    assert engine.url.database == "test_db"
    assert session_factory.kw["bind"].url == engine.url
    assert Base.metadata.tables == {}
