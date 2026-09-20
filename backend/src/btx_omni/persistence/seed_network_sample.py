"""Generate an in-memory fake network CSV and seed only a local database."""
from __future__ import annotations

import argparse
import csv
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url

from btx_omni.core.config import Settings
from btx_omni.persistence import models
from btx_omni.persistence.database import create_database_engine
from btx_omni.persistence.network_import import (
    LinkedInConnectionsCsvAdapter,
    NetworkImportRepository,
)
from btx_omni.providers.sample.environment import build_sample_environment

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class LocalFakeConnectionsAdapter(LinkedInConnectionsCsvAdapter):
    source_kind = "local_fake_network_seed"


def assert_local_database(database_url: str) -> None:
    url = make_url(database_url)
    if (url.get_backend_name() != "postgresql" or url.host not in LOCAL_HOSTS
            or any(key.casefold() in {"host", "hostaddr", "service", "servicefile"} for key in url.query)):
        raise ValueError("Fake network seeding is restricted to local PostgreSQL")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed 200 generated fake contacts into local PostgreSQL")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--owner-user-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    assert_local_database(settings.database_url)
    sample = build_sample_environment()
    engine = create_database_engine(settings)
    with engine.connect() as connection:
        existing = set(connection.scalars(select(models.accounts.c.id)))
    accounts = [account for account in sample.accounts if account.id in existing]
    if not accounts:
        raise ValueError("Load canonical accounts into the local database before seeding contacts")
    with tempfile.NamedTemporaryFile("w", suffix=".csv", newline="", encoding="utf-8", delete=False) as handle:
        path = Path(handle.name)
        writer = csv.writer(handle)
        writer.writerow(("First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On"))
        titles = ("Director of Procurement", "Supply Chain Manager", "Manufacturing Engineer", "Operations Analyst")
        for index in range(200):
            account = accounts[index % len(accounts)]
            writer.writerow(("Fake", f"Contact {index + 1:03d}", f"https://example.invalid/fake-{index + 1}", "",
                             account.legal_name, titles[index % len(titles)], "2026-09-01"))
    try:
        repository = NetworkImportRepository(engine, sample.watch_profiles)
        report = repository.import_file(path, tenant_id=args.tenant_id, owner_user_id=args.owner_user_id,
                                        owner_name="Local Fake Network Owner", exported_at=datetime(2026, 9, 1, tzinfo=UTC),
                                        adapter=LocalFakeConnectionsAdapter(), apply=args.apply)
        print("local fake network seed:", {key: value for key, value in report.items() if key not in {"batch_id", "file_sha256"}})
    finally:
        path.unlink(missing_ok=True)
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
