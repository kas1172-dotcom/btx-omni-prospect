from dataclasses import dataclass, field
from functools import lru_cache

from btx_omni.core.config import Settings
from btx_omni.persistence.ai_usage import AiUsageRepository
from btx_omni.persistence.database import create_database_engine


@lru_cache(maxsize=8)
def usage_repository(database_url: str) -> AiUsageRepository:
    return AiUsageRepository(create_database_engine(Settings(database_url=database_url)))


@dataclass(frozen=True)
class AiConfig:
    provider: str
    api_key: str | None
    model: str
    mode: str
    project: str | None
    location: str
    timeout_seconds: float
    usage: AiUsageRepository | None = field(default=None, repr=False, compare=False)
    actor_id: str = "system:monitor"
    purpose: str = "monitor"
    daily_environment_limit: int = 1000
    daily_actor_limit: int = 400
    concurrent_environment_limit: int = 2
    concurrent_actor_limit: int = 1

    @classmethod
    def from_settings(cls, settings: Settings, *, actor_id: str = "system:monitor", purpose: str = "monitor") -> "AiConfig":
        return cls(
            settings.ai_provider,
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_mode,
            settings.google_cloud_project,
            settings.google_cloud_location,
            settings.ai_timeout_seconds,
            usage=usage_repository(settings.database_url),
            actor_id=actor_id,
            purpose=purpose,
            daily_environment_limit=settings.ai_daily_environment_calls,
            daily_actor_limit=settings.ai_daily_actor_calls,
            concurrent_environment_limit=settings.ai_concurrent_environment_calls,
            concurrent_actor_limit=settings.ai_concurrent_actor_calls,
        )
