from dataclasses import dataclass

from btx_omni.core.config import Settings


@dataclass(frozen=True)
class AiConfig:
    provider: str
    anthropic_api_key: str | None
    anthropic_model: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "AiConfig":
        return cls(settings.ai_provider, settings.anthropic_api_key, settings.anthropic_model)
