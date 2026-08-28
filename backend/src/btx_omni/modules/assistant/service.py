"""Omni control plane: canonical read first, optional bounded language synthesis second."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from btx_omni.ai.contracts import (
    ConversationTurn,
    GroundedSynthesisRequest,
    IntentInterpretationRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
)
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
        recent_turns = self._recent_turns(context.get("prior_turns"))
        routing_context = dict(context)
        interpretation_failure: ProviderStatus | None = None
        if self.provider is not None and self.provider.configured:
            interpret = getattr(self.provider, "interpret", None)
            if callable(interpret):
                try:
                    interpretation = interpret(
                        IntentInterpretationRequest(question, recent_turns)
                    )
                    routing_context["_interpreted_intent"] = interpretation.intent.value
                    if interpretation.entity_text:
                        routing_context["_interpreted_entity_text"] = interpretation.entity_text
                except LanguageProviderError as error:
                    interpretation_failure = error.status
                except (RuntimeError, TimeoutError, ValueError):
                    interpretation_failure = ProviderStatus.UNAVAILABLE

        def governed(arguments: Mapping[str, object]) -> OmniResponse:
            return OmniOrchestrator().answer(
                environment,
                account_id=account_id,
                question=str(arguments["question"]),
                observed_at=observed_at,
                context=routing_context,
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
                provider_status=ProviderStatus.NOT_CONFIGURED.value,
                language_provider="deterministic",
            )
        if interpretation_failure is not None:
            return replace(
                deterministic,
                provider_status=interpretation_failure.value,
                language_provider="deterministic",
            )
        if deterministic.context_used.get("interpretation_status") == "CLARIFICATION":
            return replace(
                deterministic,
                provider_status=ProviderStatus.AVAILABLE.value,
                language_provider="deterministic",
            )
        try:
            synthesis = self.provider.synthesize(
                GroundedSynthesisRequest(
                    question,
                    deterministic.content,
                    deterministic.citations,
                    deterministic.missingness,
                    recent_turns,
                )
            )
        except LanguageProviderError as error:
            return replace(
                deterministic,
                provider_status=error.status.value,
                language_provider="deterministic",
            )
        except TimeoutError:
            return replace(
                deterministic,
                provider_status=ProviderStatus.TIMEOUT.value,
                language_provider="deterministic",
            )
        except (RuntimeError, ValueError):
            return replace(
                deterministic,
                provider_status=ProviderStatus.UNAVAILABLE.value,
                language_provider="deterministic",
            )
        return replace(
            deterministic,
            content=synthesis.content,
            language_provider=synthesis.provider,
            language_model=synthesis.model,
            provider_status=ProviderStatus.AVAILABLE.value,
        )

    @staticmethod
    def _recent_turns(value: object) -> tuple[ConversationTurn, ...]:
        """Parse bounded UI history for language continuity, never canonical resolution."""
        if not isinstance(value, str):
            return ()
        turns: list[ConversationTurn] = []
        for line in value[-1600:].splitlines():
            role, separator, content = line.partition(":")
            normalized_role = role.strip().casefold()
            if separator and normalized_role in {"user", "assistant"} and content.strip():
                turns.append(ConversationTurn(normalized_role, content.strip()[:500]))
        return tuple(turns[-6:])
