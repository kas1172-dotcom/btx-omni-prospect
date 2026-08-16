from btx_omni.ai.anthropic import AnthropicProvider
from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import AiProvider


def get_ai_provider(config: AiConfig) -> AiProvider:
    if config.provider.lower() == "anthropic":
        return AnthropicProvider(config)
    raise ValueError(f"Unsupported AI_PROVIDER: {config.provider}")
