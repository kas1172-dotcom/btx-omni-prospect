"""Optional, non-CI Gemini connectivity check without application or Customer data."""
from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import GroundedSynthesisRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.core.config import get_settings


def main() -> None:
    provider = get_ai_provider(AiConfig.from_settings(get_settings(), actor_id="system:operator", purpose="connectivity"))
    if not provider.configured:
        raise SystemExit("Gemini is not configured; see backend/.env.example.")
    result = provider.synthesize(
        GroundedSynthesisRequest(
            question="Summarize the governed status.",
            governed_answer="The optional Gemini connectivity check is configured.",
            evidence_ids=(),
            missingness=(),
        )
    )
    print(f"Gemini live validation passed: provider={result.provider} model={result.model}")


if __name__ == "__main__":
    main()
