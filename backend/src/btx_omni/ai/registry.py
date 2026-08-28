from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import LanguageProvider
from btx_omni.ai.gemini import GeminiProvider


def get_ai_provider(config: AiConfig) -> LanguageProvider:
    if config.provider.casefold() == "gemini":
        return GeminiProvider(config)
    raise ValueError(f"Unsupported AI provider: {config.provider}")
