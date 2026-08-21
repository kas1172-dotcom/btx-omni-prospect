"""Shared bounded POC runtime for API routers; CONNECTED never falls back to SAMPLE."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.core.config import Settings
from btx_omni.modules.work.service import WorkService
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, UsaSpendingAdapter
from btx_omni.monitor.usaspending import recipient_query_names, targeted_profiles
from btx_omni.persistence.database import create_database_engine
from btx_omni.persistence.durable_accounts import DurablePublicAccountRepository
from btx_omni.providers.sample.environment import (
    SampleEnvironment,
    build_sample_environment,
)


@dataclass
class PocRuntime:
    settings: Settings
    sample: SampleEnvironment = field(default_factory=build_sample_environment)
    work: WorkService = field(default_factory=WorkService)
    monitor: MonitorService = field(init=False)
    durable_accounts: DurablePublicAccountRepository | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        engine = create_database_engine(self.settings) if self.settings.monitor_durable_state_enabled else None
        repository = MonitorRepository(engine) if engine else None
        self.durable_accounts = DurablePublicAccountRepository(engine) if engine else None
        if self.durable_accounts:
            try:
                persisted = tuple(item.account for item in self.durable_accounts.accounts())
                ids = {item.id for item in self.sample.accounts}
                if ids & {item.id for item in persisted}:
                    raise ValueError("durable Account ID collides with the curated canonical universe.")
                durable_profiles = tuple(
                    AccountWatchProfile(
                        item.id,
                        item.legal_name,
                        aliases=tuple(field.value for field in item.public_identity.aliases) if item.public_identity else (),
                        domain=item.domain,
                        source_native_identifiers=tuple(
                            field.source_native_identifier
                            for field in item.public_identity.source_native_identifiers
                            if field.source_native_identifier
                        ) if item.public_identity else (),
                        industries=item.industries,
                    )
                    for item in persisted
                )
                self.sample = replace(
                    self.sample,
                    accounts=(*self.sample.accounts, *persisted),
                    identity_map={
                        **self.sample.identity_map,
                        **{f"public:{item.legal_name.casefold()}": item.id for item in persisted},
                    },
                    watch_profiles=(*self.sample.watch_profiles, *durable_profiles),
                )
            except SQLAlchemyError:
                self.durable_accounts = None
        usa_profiles = targeted_profiles(self.sample.watch_profiles, rich_account_ids=set(self.sample.rich_scenarios))
        registry = dict(REGISTRY)
        registry["usaspending"] = UsaSpendingAdapter(recipient_names=recipient_query_names(usa_profiles))
        self.monitor = MonitorService(
            self.settings,
            registry=registry,
            repository=repository,
            watch_profiles=usa_profiles,
            catalog=MonitorCatalog(self.sample.watch_profiles, self.sample.programs, self.sample.facilities),
        )
        if repository:
            try:
                self.monitor.hydrate_events()
            except SQLAlchemyError:
                # The Monitor health route retains the existing durable-state
                # unavailable/degraded behavior; do not fabricate live events.
                pass

    def environment(self) -> SampleEnvironment:
        if self.settings.data_mode.upper() != "SAMPLE":
            raise HTTPException(503, "CONNECTED mode is unavailable: no live providers are configured.")
        return self.sample

    @staticmethod
    def observed_at() -> datetime:
        # The curated SAMPLE commercial snapshot and its governed alerts are anchored here.
        return datetime(2026, 8, 31, tzinfo=UTC)
