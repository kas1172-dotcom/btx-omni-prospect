"""Omni control plane: canonical read first, optional bounded language synthesis second."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from btx_omni.ai.contracts import GroundedSynthesisRequest, LanguageProvider
from btx_omni.modules.assistant.orchestration import OmniOrchestrator, OmniResponse
from btx_omni.modules.assistant.tools import GovernedReadTools, ToolCall
from btx_omni.providers.sample.environment import SampleEnvironment


class OmniService:
    def __init__(self, provider: LanguageProvider | None = None) -> None:
        self.provider = provider

    def answer(
        self,
        environment: SampleEnvironment,
        *,
        account_id: str | None,
        question: str,
        observed_at,
        context: dict[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
    ) -> OmniResponse:
        def governed(arguments: Mapping[str, object]) -> OmniResponse:
            return OmniOrchestrator().answer(
                environment,
                account_id=account_id,
                question=str(arguments["question"]),
                observed_at=observed_at,
                context=context,
                intelligence_events=intelligence_events,
                work_items=work_items,
            )

        deterministic = GovernedReadTools(governed).execute(
            (ToolCall("resolve_governed_context", {"question": question}),)
        )[0]
        assert isinstance(deterministic, OmniResponse)
        if self.provider is None or not self.provider.configured:
            return replace(
                deterministic,
                provider_status="NOT_CONFIGURED",
                language_provider="deterministic",
            )
        try:
            synthesis = self.provider.synthesize(
                GroundedSynthesisRequest(
                    question,
                    deterministic.content,
                    deterministic.citations,
                    deterministic.missingness,
                )
            )
        except (RuntimeError, TimeoutError, ValueError):
            return replace(
                deterministic,
                provider_status="UNAVAILABLE",
                language_provider="deterministic",
            )
        return replace(
            deterministic,
            content=synthesis.content,
            language_provider=synthesis.provider,
            language_model=synthesis.model,
            provider_status="AVAILABLE",
        )
