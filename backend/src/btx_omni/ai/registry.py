from dataclasses import replace

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import LanguageProvider
from btx_omni.ai.gemini import GeminiProvider


def get_ai_provider(config: AiConfig) -> LanguageProvider:
    if config.provider.casefold() == "gemini":
        return GeminiProvider(config)
    # Configuration may reference a retired provider.  Preserve fail-closed AI
    # behavior by returning the configured Gemini adapter (normally unconfigured)
    # instead of crashing a persisted-read route or the Monitor worker.
    return GeminiProvider(replace(config, provider="gemini", api_key=None))
