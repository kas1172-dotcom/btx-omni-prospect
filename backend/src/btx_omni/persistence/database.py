from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from btx_omni.core.config import Settings


class Base(DeclarativeBase):
    pass


def create_database_engine(settings: Settings) -> Engine:
    """Create the application's SQLAlchemy engine without opening a connection."""
    options: dict[str, object] = {"pool_pre_ping": True}
    if make_url(settings.database_url).get_backend_name() == "postgresql":
        # Durable Monitor availability is optional at local startup. Bound an
        # unavailable PostgreSQL handshake so the existing degraded health path
        # can report it instead of blocking the application indefinitely.
        connect_args: dict[str, object] = {"connect_timeout": 3}
        options["connect_args"] = connect_args
    engine = create_engine(settings.database_url, **options)
    if (
        make_url(settings.database_url).get_backend_name() == "postgresql"
        and settings.monitor_worker_timeouts_enabled
    ):
        statement_timeout = settings.monitor_worker_statement_timeout_ms
        lock_timeout = settings.monitor_worker_lock_timeout_ms

        @event.listens_for(engine, "begin")
        def set_worker_transaction_timeouts(connection) -> None:
            connection.exec_driver_sql(
                f"SET LOCAL statement_timeout = '{statement_timeout}ms'"
            )
            connection.exec_driver_sql(f"SET LOCAL lock_timeout = '{lock_timeout}ms'")

    return engine


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_database_engine(settings),
        autoflush=False,
        expire_on_commit=False,
    )


@lru_cache
def get_engine() -> Engine:
    from btx_omni.core.config import get_settings

    return create_database_engine(get_settings())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    from btx_omni.core.config import get_settings

    return create_session_factory(get_settings())


def get_db_session() -> Generator[Session, None, None]:
    """Yield a session for FastAPI dependencies once database-backed routes exist."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
