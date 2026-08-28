from dataclasses import dataclass

from btx_omni.core.config import Settings


@dataclass(frozen=True)
class AiConfig:
    provider: str
    api_key: str | None
    model: str
    mode: str
    project: str | None
    location: str
    timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "AiConfig":
        return cls(
            settings.ai_provider,
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_mode,
            settings.google_cloud_project,
            settings.google_cloud_location,
            settings.ai_timeout_seconds,
        )
