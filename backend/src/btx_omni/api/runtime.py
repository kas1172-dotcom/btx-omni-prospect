"""Shared bounded POC runtime for API routers; CONNECTED never falls back to SAMPLE."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException

from btx_omni.core.config import Settings
from btx_omni.modules.work.service import WorkService
from btx_omni.providers.sample.environment import (
    SampleEnvironment,
    build_sample_environment,
)


@dataclass
class PocRuntime:
    settings: Settings
    sample: SampleEnvironment = field(default_factory=build_sample_environment)
    work: WorkService = field(default_factory=WorkService)

    def environment(self) -> SampleEnvironment:
        if self.settings.data_mode.upper() != "SAMPLE":
            raise HTTPException(503, "CONNECTED mode is unavailable: no live providers are configured.")
        return self.sample

    @staticmethod
    def observed_at() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)
