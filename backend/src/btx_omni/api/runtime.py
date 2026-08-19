"""Shared bounded POC runtime for API routers; CONNECTED never falls back to SAMPLE."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException

from btx_omni.core.config import Settings
from btx_omni.modules.work.service import WorkService
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, UsaSpendingAdapter
from btx_omni.monitor.usaspending import recipient_query_names, targeted_profiles
from btx_omni.persistence.database import create_database_engine
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

    def __post_init__(self) -> None:
        repository = MonitorRepository(create_database_engine(self.settings)) if self.settings.monitor_durable_state_enabled else None
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

    def environment(self) -> SampleEnvironment:
        if self.settings.data_mode.upper() != "SAMPLE":
            raise HTTPException(503, "CONNECTED mode is unavailable: no live providers are configured.")
        return self.sample

    @staticmethod
    def observed_at() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)
