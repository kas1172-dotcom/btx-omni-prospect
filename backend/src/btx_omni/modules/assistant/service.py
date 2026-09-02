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
    PublicWebResearchRequest,
)
from btx_omni.modules.assistant.orchestration import (
    AssistantProvenance,
    OmniCitation,
    OmniOrchestrator,
    OmniResponse,
)
from btx_omni.modules.assistant.public_research import should_research_public_web
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
                        routing_context["_interpreted_entity_text"] = (
                            interpretation.entity_text
                        )
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
        public_findings = ()
        public_limitations: tuple[str, ...] = ()
        research_failure: ProviderStatus | None = None
        research = getattr(self.provider, "research_public_web", None)
        if should_research_public_web(question):
            if callable(research):
                try:
                    subject = deterministic.account_name
                    research_result = research(
                        PublicWebResearchRequest(
                            query=question,
                            subject_display_name=subject,
                            governed_context=(deterministic.content[:600],),
                        )
                    )
                    public_findings = research_result.findings
                    public_limitations = research_result.limitations
                except LanguageProviderError as error:
                    research_failure = error.status
                except (RuntimeError, TimeoutError, ValueError):
                    research_failure = ProviderStatus.UNAVAILABLE
            else:
                research_failure = ProviderStatus.UNAVAILABLE
        enriched = deterministic
        if public_findings:
            findings_text = " ".join(
                f"Public-web finding ({item.publisher}): {item.title}. "
                "Its cited content remains public information, not a governed Omni fact."
                for item in public_findings
            )
            enriched = replace(
                deterministic,
                content=f"{deterministic.content}\n\nCurrent public-web findings: {findings_text}",
                citations=tuple(
                    dict.fromkeys(
                        (
                            *deterministic.citations,
                            *(item.evidence_id for item in public_findings),
                        )
                    )
                ),
                citation_links=(
                    *deterministic.citation_links,
                    *(OmniCitation(item.title, item.url) for item in public_findings),
                ),
                provenance=tuple(
                    dict.fromkeys(
                        (
                            *deterministic.provenance,
                            AssistantProvenance.LIVE_PUBLIC_RESEARCH,
                        )
                    )
                ),
                missingness=tuple(
                    dict.fromkeys((*deterministic.missingness, *public_limitations))
                ),
                context_used={
                    **deterministic.context_used,
                    "public_web_research": "CITED_PUBLIC_FINDINGS",
                },
            )
        elif research_failure is not None:
            enriched = replace(
                deterministic,
                missingness=tuple(
                    dict.fromkeys(
                        (
                            *deterministic.missingness,
                            "Current public-web research was unavailable; governed Omni context remains available.",
                        )
                    )
                ),
                context_used={
                    **deterministic.context_used,
                    "public_web_research": "UNAVAILABLE",
                },
            )
        try:
            synthesis = self.provider.synthesize(
                GroundedSynthesisRequest(
                    question,
                    enriched.content,
                    enriched.citations,
                    enriched.missingness,
                    recent_turns,
                    public_findings,
                )
            )
        except LanguageProviderError as error:
            return replace(
                enriched,
                provider_status=error.status.value,
                language_provider="deterministic",
            )
        except TimeoutError:
            return replace(
                enriched,
                provider_status=ProviderStatus.TIMEOUT.value,
                language_provider="deterministic",
            )
        except (RuntimeError, ValueError):
            return replace(
                enriched,
                provider_status=ProviderStatus.UNAVAILABLE.value,
                language_provider="deterministic",
            )
        return replace(
            enriched,
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
            if (
                separator
                and normalized_role in {"user", "assistant"}
                and content.strip()
            ):
                turns.append(ConversationTurn(normalized_role, content.strip()[:500]))
        return tuple(turns[-6:])
