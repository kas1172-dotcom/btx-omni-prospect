"""Failure-path checks for the one-shot Monitor worker's time bounds."""

import os
import subprocess
import sys
import time
from threading import Event
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.core.config import Settings
from btx_omni.modules.markets.service import MarketService
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.worker import run_worker
from btx_omni.persistence.database import create_database_engine


def _database_settings() -> Settings:
    url = os.environ.get("BTX_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL is not configured")
    return Settings(_env_file=None, database_url=url)


def test_worker_database_statement_timeout_cancels_a_blocked_query() -> None:
    settings = _database_settings()
    bounded = settings.model_copy()
    bounded._worker_database_timeouts_ms = (100, 50)
    engine = create_database_engine(bounded)
    api_engine = create_database_engine(settings)
    try:
        with api_engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "0"
            assert connection.execute(text("SHOW lock_timeout")).scalar_one() == "0"
        with engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "100ms"
            assert connection.execute(text("SHOW lock_timeout")).scalar_one() == "50ms"
            started = time.monotonic()
            with pytest.raises(SQLAlchemyError, match="statement timeout"):
                connection.execute(text("SELECT pg_sleep(1)"))
            assert time.monotonic() - started < 0.8
    finally:
        engine.dispose()
        api_engine.dispose()


def test_worker_database_lock_timeout_cancels_a_blocked_lock() -> None:
    settings = _database_settings()
    bounded = settings.model_copy()
    bounded._worker_database_timeouts_ms = (500, 50)
    holder_engine = create_database_engine(settings)
    waiter_engine = create_database_engine(bounded)
    key = int.from_bytes(os.urandom(8), "big") & ((1 << 63) - 1)
    try:
        with holder_engine.begin() as holder, waiter_engine.connect() as waiter:
            holder.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            started = time.monotonic()
            with pytest.raises(SQLAlchemyError, match="lock timeout"):
                waiter.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            assert time.monotonic() - started < 0.4
    finally:
        holder_engine.dispose()
        waiter_engine.dispose()


def test_operational_lock_release_does_not_wait_for_stuck_heartbeat() -> None:
    heartbeat_entered = Event()
    release_heartbeat = Event()

    class Connection:
        def __init__(self):
            self.statements: list[str] = []
            self.health_checks = 0
            self.closed = False

        def execution_options(self, **_options):
            return self

        def execute(self, statement):
            sql = str(statement)
            self.statements.append(sql)
            if sql == "SELECT 1":
                self.health_checks += 1
                if self.health_checks == 2:
                    heartbeat_entered.set()
                    release_heartbeat.wait(timeout=2)
            return SimpleNamespace(scalar_one=lambda: True)

        def close(self):
            self.closed = True

    connection = Connection()
    repository = MonitorRepository.__new__(MonitorRepository)
    repository.engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=lambda: connection
    )
    started = time.monotonic()
    try:
        with (
            pytest.raises(RuntimeError, match="heartbeat release timed out"),
            repository.operational_lock(
                heartbeat_interval_seconds=0.001, release_timeout_seconds=0.05
            ),
        ):
            assert heartbeat_entered.wait(timeout=1)
        assert time.monotonic() - started < 0.5
        assert not connection.closed
        assert not any("pg_advisory_unlock" in sql for sql in connection.statements)
    finally:
        release_heartbeat.set()


def test_operational_unlock_has_its_own_statement_timeout() -> None:
    class Connection:
        def __init__(self):
            self.statements: list[str] = []
            self.closed = False

        def execution_options(self, **_options):
            return self

        def execute(self, statement):
            sql = str(statement)
            self.statements.append(sql)
            if "pg_advisory_unlock" in sql:
                raise SQLAlchemyError("statement timeout")
            return SimpleNamespace(scalar_one=lambda: True)

        def close(self):
            self.closed = True

    connection = Connection()
    repository = MonitorRepository.__new__(MonitorRepository)
    repository.engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=lambda: connection
    )
    with (
        pytest.raises(RuntimeError, match="unlock failed"),
        repository.operational_lock(release_timeout_seconds=0.05),
    ):
        pass
    assert "SET statement_timeout = '50ms'" in connection.statements
    assert connection.closed


def test_hard_deadline_ends_blocked_process() -> None:
    script = (
        "import time\n"
        "from btx_omni.monitor.worker import _hard_process_deadline\n"
        "with _hard_process_deadline(0.1):\n"
        "    time.sleep(10)\n"
        "print('continued')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 124
    assert "hard deadline exceeded" in result.stderr
    assert "continued" not in result.stdout


def test_hard_exit_releases_postgres_session_advisory_lock() -> None:
    settings = _database_settings()
    key = int.from_bytes(os.urandom(8), "big") & ((1 << 63) - 1)
    script = (
        "import time\n"
        "from sqlalchemy import text\n"
        "from btx_omni.core.config import Settings\n"
        "from btx_omni.monitor.worker import _hard_process_deadline\n"
        "from btx_omni.persistence.database import create_database_engine\n"
        "engine = create_database_engine(Settings(_env_file=None))\n"
        "with engine.connect() as connection:\n"
        f"    connection.execute(text('SELECT pg_advisory_lock({key})'))\n"
        "    with _hard_process_deadline(0.1):\n"
        "        time.sleep(10)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 124
    engine = create_database_engine(settings)
    try:
        until = time.monotonic() + 2
        acquired = False
        while time.monotonic() < until and not acquired:
            with engine.connect() as connection:
                acquired = bool(
                    connection.execute(
                        text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                    ).scalar_one()
                )
                if acquired:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                    )
            if not acquired:
                time.sleep(0.05)
        assert acquired, "Dead worker retained its PostgreSQL session lock"
    finally:
        engine.dispose()


def test_market_refresh_checks_deadline_before_database_health() -> None:
    service = MarketService(
        SimpleNamespace(health=lambda: pytest.fail("health read started after deadline")),
        worker_enabled=True,
    )
    assert service.worker_refresh(deadline_monotonic=time.monotonic() + 1)[
        "status"
    ] == "SKIPPED_DEADLINE"


def test_worker_sql_limits_are_not_added_to_caller_settings(monkeypatch) -> None:
    captured = []

    class Runtime:
        def __init__(self, settings):
            captured.append(settings._worker_database_timeouts_ms)
            self.monitor = SimpleNamespace(repository=None, registry={})

    monkeypatch.setattr("btx_omni.monitor.worker.PocRuntime", Runtime)
    settings = Settings(
        _env_file=None, monitor_mode="live", monitor_durable_state_enabled=True
    )
    run_worker(settings)
    assert captured == [(15_000, 5_000)]
    assert settings._worker_database_timeouts_ms is None
