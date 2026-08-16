from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from btx_omni.core.config import Settings


class Base(DeclarativeBase):
    pass


def create_database_engine(settings: Settings) -> Engine:
    """Create the application's SQLAlchemy engine without opening a connection."""
    return create_engine(settings.database_url, pool_pre_ping=True)


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
