"""Omni control plane: canonical read first, optional bounded language synthesis second."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace

from btx_omni.ai.contracts import (
    ConversationTurn,
    GroundedSynthesisRequest,
    IntentInterpretationRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
    PublicEvidenceRecord,
    PublicWebFinding,
)
from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.modules.assistant.grounding import synthesis_rejection
from btx_omni.modules.assistant.orchestration import (
    AssistantProvenance,
    OmniCitation,
    OmniOrchestrator,
    OmniResponse,
)
from btx_omni.modules.assistant.public_research import (
    safe_public_research_request,
    should_research_public_web,
)
from btx_omni.modules.assistant.relationship_context import (
    selected_relationship_context,
)
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
        memory_reader: Callable[[str | None], list[dict]] | None = None,
        public_evidence_reader: Callable[
            [str, str | None], tuple[PublicEvidenceRecord, ...]
        ]
        | None = None,
        market_reader: Callable[[dict], dict] | None = None,
    ) -> OmniResponse:
        intelligence_events = tuple(intelligence_events)
        operational_contract = self._operational_contract(question)
        recent_turns = self._recent_turns(context.get("prior_turns"))
        work_items = tuple(work_items)
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
        selected_assessment = self._selected_assessment_contract(
            intelligence_events, deterministic
        )
        market_filters = context.get("active_filters")
        if isinstance(market_filters, dict) and "market_series_id" in market_filters:
            try:
                if market_reader is None:
                    raise ValueError("Market context reader is unavailable.")
                market_context = market_reader(market_filters)
            except (ValueError, KeyError, TypeError):
                return replace(
                    deterministic,
                    content="The selected market series is unavailable, stale or incompatible. Refresh Market Intelligence before asking for an explanation.",
                    recommended_action=None,
                    context_used={
                        **deterministic.context_used,
                        "market_context": "STALE_OR_UNAVAILABLE",
                    },
                )
            deterministic = replace(
                deterministic,
                content=market_context["content"],
                structured_market=market_context,
                citation_links=(
                    *deterministic.citation_links,
                    OmniCitation(
                        "Federal Reserve Board market observations",
                        market_context["source_url"],
                    ),
                ),
                citations=(*deterministic.citations, market_context["vintage_id"]),
                recommended_action="Inspect exposed accounts' actual RFQs and delivery constraints before a local follow-up.",
                context_used={
                    **deterministic.context_used,
                    "market_context": "CANONICAL_CURRENT_VINTAGE",
                    "interpretation_status": "RESOLVED",
                    "market_vintage_id": market_context["vintage_id"],
                },
            )
        selection = context.get("relationship_selection")
        if isinstance(
            selection, dict
        ) and OmniOrchestrator.should_apply_relationship_selection(question, context):
            try:
                structured = selected_relationship_context(
                    environment, selection, account_id=account_id
                )
                source_account_id = selection["source_account_id"]
                source_account = next(
                    account
                    for account in environment.accounts
                    if account.id == source_account_id
                )
            except (KeyError, ValueError, PermissionError):
                return replace(
                    deterministic,
                    content="The selected relationship context is unavailable, stale or outside the requested account scope. Refresh the route before asking Omni to explain it.",
                    missingness=(
                        "Selected relationship requires a current authorized canonical resolution.",
                    ),
                    recommended_action=None,
                    context_used={
                        **deterministic.context_used,
                        "relationship_selection": "STALE_OR_UNAVAILABLE",
                    },
                )
            deterministic = replace(
                deterministic,
                content=structured["content"],
                account_id=source_account.id,
                account_name=source_account.legal_name,
                citations=tuple(structured["route"]["evidence_ids"]),
                citation_links=tuple(
                    OmniCitation(item["label"], item["url"])
                    for item in structured.get("source_links", ())
                ),
                recommended_action=structured["route"]["next_action"],
                structured_relationship=structured,
                context_used={
                    **deterministic.context_used,
                    "relationship_path_id": selection["path_id"],
                    "graph_revision": structured["graph_revision"],
                },
            )
        memories = memory_reader(deterministic.account_id) if memory_reader else []
        # Explicit preferences are retrieved only after canonical account and selected
        # relationship scope resolution. They are not passed to intent selection,
        # public search, tools or score owners.
        preferences = tuple(f"{m['kind']}: {m['content']}" for m in memories[:8])
        if memories:
            deterministic = replace(
                deterministic,
                context_used={
                    **deterministic.context_used,
                    "private_memory_ids": [m["id"] for m in memories[:8]],
                    "private_memory_omitted": max(0, len(memories) - 8),
                },
            )
        stored_findings = ()
        selected_event_id = context.get("selected_event_id")
        if public_evidence_reader and isinstance(selected_event_id, str):
            stored = public_evidence_reader(selected_event_id, deterministic.account_id)
            stored_findings = tuple(
                PublicWebFinding(
                    item.evidence_id,
                    item.title,
                    item.source_url,
                    "Persisted public document",
                    item.extract,
                    "PERSISTED_MONITOR_PASSAGE " + (item.provenance or ""),
                )
                for item in stored
                if item.source_url
            )
            deterministic = replace(
                deterministic,
                citations=tuple(
                    dict.fromkeys(
                        (
                            *deterministic.citations,
                            *(item.evidence_id for item in stored_findings),
                        )
                    )
                ),
                context_used={
                    **deterministic.context_used,
                    **(
                        {
                            "selected_public_passages": len(stored_findings),
                            "selected_public_evidence_status": "PERSISTED_SCOPED_EVIDENCE",
                        }
                        if stored_findings
                        else {}
                    ),
                },
                missingness=deterministic.missingness
                + (
                    ()
                    if stored_findings
                    else (
                        "No retained public passages were available for this event and account scope.",
                    )
                ),
            )
        if self.provider is None or not self.provider.configured:
            return self._apply_operational_contract(
                replace(
                    deterministic,
                    provider_status=ProviderStatus.NOT_CONFIGURED.value,
                    language_provider="deterministic",
                ),
                operational_contract,
            )
        if interpretation_failure is not None:
            return self._apply_operational_contract(
                replace(
                    deterministic,
                    provider_status=interpretation_failure.value,
                    language_provider="deterministic",
                ),
                operational_contract,
            )
        if deterministic.context_used.get("interpretation_status") == "CLARIFICATION":
            return replace(
                deterministic,
                provider_status=ProviderStatus.AVAILABLE.value,
                language_provider="deterministic",
            )
        retrieval = None
        retrieval_notice = None
        if (
            selected_assessment is None
            and deterministic.account_id in environment.commercial_ledgers
            and callable(getattr(self.provider, "choose_canonical_read", None))
        ):
            retrieval = CommercialToolSession(
                environment,
                deterministic.account_id,
                work_items=work_items,
                selected_relationship=deterministic.structured_relationship,
                selected_market=deterministic.structured_market,
            ).run(self.provider, question)
            deterministic = replace(
                deterministic,
                structured_reads=retrieval,
                citations=tuple(
                    dict.fromkeys(
                        (
                            *deterministic.citations,
                            *(
                                eid
                                for step in retrieval["steps"]
                                for eid in step["evidence_ids"]
                            ),
                        )
                    )
                ),
                context_used={
                    **deterministic.context_used,
                    "canonical_read_steps": len(retrieval["steps"]),
                    "canonical_read_stop_reason": retrieval["stop_reason"],
                },
            )
            missing_records = [
                read["result"]["record_id"]
                for read in retrieval["reads"]
                if read["tool"] == "read_evidence"
                and read["result"].get("status") == "NOT_FOUND_IN_ACCOUNT"
            ]
            if missing_records:
                lookup_notice = (
                    "No matching record was found in this account for: "
                    + ", ".join(missing_records)
                    + ". Associated payment dates and amounts are unknown; this does not establish global absence."
                )
                lookup_action = (
                    "Ask the requester for the correct record reference or supporting document, "
                    "then repeat the account-scoped lookup. Do not substitute another record."
                )
                deterministic = replace(
                    deterministic,
                    content=lookup_notice
                    + "\nNext useful action: "
                    + lookup_action
                    + (
                        "\n\n" + deterministic.content
                        if len(retrieval["reads"]) > len(missing_records)
                        else ""
                    ),
                    recommended_action=lookup_action
                    if len(retrieval["reads"]) == len(missing_records)
                    else deterministic.recommended_action,
                    missingness=(*deterministic.missingness, lookup_notice),
                )
            if retrieval["stop_reason"] != "MODEL_DONE":
                retrieval_notice = "This answer is limited to completed record reads; further retrieval stopped before all requested checks were confirmed."
                deterministic = replace(
                    deterministic,
                    content=retrieval_notice + "\n\n" + deterministic.content,
                    missingness=(*deterministic.missingness, retrieval_notice),
                    context_used={
                        **deterministic.context_used,
                        "canonical_retrieval_status": "PARTIAL",
                    },
                )
        public_findings = stored_findings
        public_limitations: tuple[str, ...] = ()
        research_failure: ProviderStatus | None = None
        research = getattr(self.provider, "research_public_web", None)
        if should_research_public_web(
            question, has_selected_evidence=bool(stored_findings)
        ):
            public_subject = next(
                (
                    a.legal_name
                    for a in environment.accounts
                    if a.id == deterministic.account_id
                ),
                None,
            )
            if callable(research) and public_subject:
                try:
                    research_result = research(
                        safe_public_research_request(question, public_subject)
                    )
                    public_findings = (*public_findings, *research_result.findings)
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
                f"Public evidence ({item.publisher}): {item.title}. "
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
        from btx_omni.modules.commercial.money import model_money_projection

        model_reads = (
            model_money_projection(
                retrieval["reads"],
                currency=environment.commercial_ledgers[deterministic.account_id][
                    "currency"
                ],
            )
            if retrieval
            else None
        )
        synthesis_request = GroundedSynthesisRequest(
            question,
            enriched.content
            + (
                "\nExpanded canonical evidence:\n"
                + enriched.structured_relationship["expanded_content"]
                if enriched.structured_relationship
                else ""
            )
            + (
                "\nCanonical public market series (macro context only; no score changes/customer orders/region allocation):\n"
                + json.dumps(enriched.structured_market)
                if enriched.structured_market
                else ""
            )
            + (
                "\nAdditional scoped canonical tool reads (money display and major_units are already scaled by server code; do not rescale. Preserve currency and quoted/shipped/accepted/revenue distinctions):\n"
                + json.dumps(model_reads, default=str)
                if retrieval
                else ""
            )
            + (
                "\nAuthoritative selected Intelligence assessment (do not replace its score or action):\n"
                + self._assessment_grounding(selected_assessment)
                if selected_assessment
                else ""
            )
            + (
                "\nServer-owned operational boundary (preserve this outcome and do not substitute an unrelated next action):\n"
                + operational_contract[1]
                + "\nRequired next action: "
                + operational_contract[2]
                if operational_contract
                else ""
            ),
            enriched.citations,
            enriched.missingness,
            recent_turns,
            public_findings,
            preferences,
        )
        try:
            synthesis = self.provider.synthesize(synthesis_request)
        except LanguageProviderError as error:
            return self._apply_operational_contract(
                replace(
                    enriched,
                    provider_status=error.status.value,
                    language_provider="deterministic",
                ),
                operational_contract,
            )
        except TimeoutError:
            return self._apply_operational_contract(
                replace(
                    enriched,
                    provider_status=ProviderStatus.TIMEOUT.value,
                    language_provider="deterministic",
                ),
                operational_contract,
            )
        except (RuntimeError, ValueError):
            return self._apply_operational_contract(
                replace(
                    enriched,
                    provider_status=ProviderStatus.UNAVAILABLE.value,
                    language_provider="deterministic",
                ),
                operational_contract,
            )
        validation_details = {}
        rejection = synthesis_rejection(
            synthesis.content,
            synthesis_request.governed_answer
            + "\n"
            + "\n".join(
                f.extract + "\n" + f.retrieval_provenance for f in public_findings
            ),
            blocking_constraints=bool(
                enriched.structured_relationship
                and enriched.structured_relationship["route"]["constraints"]
            ),
            diagnostics=validation_details,
        )
        if rejection:
            return self._apply_operational_contract(
                replace(
                    enriched,
                    language_provider="deterministic",
                    provider_status=ProviderStatus.UNAVAILABLE.value,
                    context_used={
                        **enriched.context_used,
                        "synthesis_validation": rejection,
                        "synthesis_validation_details": validation_details,
                    },
                    missingness=(
                        *enriched.missingness,
                        "Model wording did not pass the evidence checks; the canonical answer and completed reads remain available.",
                    ),
                ),
                operational_contract,
            )
        assessment_rejection = self._assessment_synthesis_rejection(
            synthesis.content, selected_assessment
        )
        if assessment_rejection:
            return self._apply_operational_contract(
                replace(
                    enriched,
                    language_provider="deterministic",
                    provider_status=ProviderStatus.UNAVAILABLE.value,
                    context_used={
                        **enriched.context_used,
                        "assessment_synthesis_validation": assessment_rejection,
                    },
                    missingness=(
                        *enriched.missingness,
                        "Model wording did not preserve the selected Intelligence assessment; the canonical assessment is shown unchanged.",
                    ),
                ),
                operational_contract,
            )
        return self._apply_operational_contract(
            replace(
                enriched,
                content=(
                    retrieval_notice + "\n\n"
                    if retrieval_notice
                    and not synthesis.content.startswith(retrieval_notice)
                    else ""
                )
                + synthesis.content,
                language_provider=synthesis.provider,
                language_model=synthesis.model,
                provider_status=ProviderStatus.AVAILABLE.value,
            ),
            operational_contract,
        )

    @staticmethod
    def _selected_assessment_contract(
        events: tuple[Mapping[str, object], ...], response: OmniResponse
    ) -> Mapping[str, object] | None:
        assessment_id = response.context_used.get("assessment_id")
        assessment_version = response.context_used.get("assessment_version")
        event_id = response.context_used.get("event_id")
        account_id = response.context_used.get("account_id")
        if not (
            isinstance(assessment_id, str)
            and isinstance(assessment_version, int)
            and isinstance(event_id, str)
        ):
            return None
        for event in events:
            business = event.get("business_briefing")
            if (
                event.get("id") == event_id
                and event.get("account_id") == account_id
                and isinstance(business, Mapping)
                and business.get("assessment_id") == assessment_id
                and business.get("assessment_version") == assessment_version
            ):
                return business
        return None

    @staticmethod
    def _assessment_grounding(assessment: Mapping[str, object]) -> str:
        confidence = assessment.get("signal_confidence")
        score = confidence.get("score") if isinstance(confidence, Mapping) else None
        factors = (
            confidence.get("factors", ()) if isinstance(confidence, Mapping) else ()
        )
        factor_lines = "\n".join(
            f"- {str(item.get('key', 'factor')).replace('_', ' ').title()}: "
            f"{item.get('points') if item.get('points') is not None else 'unavailable'}/100 — {item.get('reason')}"
            for item in factors
            if isinstance(item, Mapping)
        )
        package = assessment.get("evidence_package")
        technical = (
            package.get("technical_decomposition")
            if isinstance(package, Mapping)
            and isinstance(package.get("technical_decomposition"), Mapping)
            else assessment.get("technical_opportunity")
        )
        technical_lines = OmniService._technical_assessment_grounding(technical)
        return "\n".join(
            (
                f"Assessment version: {assessment.get('assessment_version')}",
                f"Headline: {assessment.get('headline')}",
                f"Verified change: {assessment.get('what_happened')}",
                f"Account-specific implication: {assessment.get('why_it_may_matter')}",
                f"Signal Confidence: {float(score):.2f}/100"
                if score is not None
                else "Signal Confidence: unavailable",
                factor_lines,
                technical_lines,
                f"Governed action: {assessment.get('recommended_action') or 'No seller action is established.'}",
                "The governed action above must be retained verbatim as the final next step. Do not introduce a different action.",
                "Use human-readable labels. Never include internal record identifiers in normal prose.",
            )
        )

    @staticmethod
    def _technical_assessment_grounding(value: object) -> str:
        if not isinstance(value, Mapping):
            return "Technical decomposition: unavailable; do not invent components or a fit."
        components = value.get("components", ())
        fits = value.get("fit_hypotheses", ())
        lines = ["Governed component hierarchy (preserve evidence layers):"]
        for component in components if isinstance(components, (list, tuple)) else ():
            if not isinstance(component, Mapping):
                continue
            parent = component.get("parent_component")
            lines.append(
                f"- {component.get('name')}"
                + (f" under {parent}" if parent else "")
                + f" — {str(component.get('evidence_layer', 'INCOMPLETE')).replace('_', ' ').title()}"
            )
        lines.append(
            "Possible BTX fit (hypotheses only; never describe as supply, award, or participation):"
        )
        for fit in fits if isinstance(fits, (list, tuple)) else ():
            if isinstance(fit, Mapping):
                lines.append(f"- {fit.get('statement')}")
        citations = value.get("citations", ())
        if isinstance(citations, (list, tuple)):
            for citation in citations:
                if isinstance(citation, Mapping) and citation.get("url"):
                    lines.append(
                        f"- Source: {citation.get('title')} — {citation.get('url')}"
                    )
        return "\n".join(lines)

    @staticmethod
    def _assessment_synthesis_rejection(
        content: str, assessment: Mapping[str, object] | None
    ) -> str | None:
        if assessment is None:
            return None
        confidence = assessment.get("signal_confidence")
        score = confidence.get("score") if isinstance(confidence, Mapping) else None
        if score is not None:
            rendered = f"{float(score):.2f}".rstrip("0").rstrip(".")
            if rendered not in content or "signal confidence" not in content.casefold():
                return "SELECTED_ASSESSMENT_SCORE_NOT_PRESERVED"
        action = assessment.get("recommended_action")
        if isinstance(action, str) and action.strip():
            normalized_action = " ".join(action.casefold().split()).rstrip(".")
            normalized_content = " ".join(content.casefold().split())
            if normalized_action not in normalized_content:
                return "SELECTED_ASSESSMENT_ACTION_NOT_PRESERVED"
        elif re.search(
            r"\b(?:next|recommended)\s+(?:step|action)\s*:",
            content,
            re.IGNORECASE,
        ):
            return "INFORMATIONAL_ASSESSMENT_ACTION_INVENTED"
        if re.search(
            r"\b(?:ROLE|QUO|ORD|SHP|INV|REV|MON|OPP|PLAN|INT|ACT)\d*-[A-Z0-9]+(?:-[A-Z0-9]+)+\b",
            content,
        ):
            return "INTERNAL_IDENTIFIER_EXPOSED"
        return None

    @staticmethod
    def _apply_operational_contract(
        response: OmniResponse,
        contract: tuple[str, str, str] | None,
    ) -> OmniResponse:
        if not contract:
            return response
        contract_key, disclosure, contract_action = contract
        marker = "Operational boundary: " + disclosure
        content = (
            response.content
            if marker in response.content
            else response.content.rstrip() + "\n\n" + marker
        )
        return replace(
            response,
            content=content,
            recommended_action=contract_action,
            context_used={
                **response.context_used,
                "operational_contract": contract_key,
                "operational_outcome": "NO_EXTERNAL_OR_CANONICAL_WRITE",
            },
        )

    @staticmethod
    def _operational_contract(question: str) -> tuple[str, str, str] | None:
        """Return a narrow server-owned outcome for bounded high-risk intents.

        Gemini still selects reads and explains the evidence. This layer keeps the
        action field, prose, and actual read-only execution outcome consistent.
        """
        query = question.casefold()
        if ("send" in query or "email" in query or "commit" in query) and (
            "buyer" in query or "recipient" in query or "deliverable" in query
        ):
            return (
                "OUTBOUND_COMMITMENT_REQUIRES_APPROVAL",
                "No email, CRM write, buyer commitment, or external delivery was performed. A proposed date is not buyer acceptance, and a deliverable recipient must be verified before an approved send.",
                "Prepare a reviewable local draft, verify buyer acceptance and a deliverable recipient, and obtain approval before any send or commitment.",
            )
        if (
            "remember" in query
            or "save my preference" in query
            or "store my preference" in query
        ) and ("score" in query or "pwin" in query or "official" in query):
            return (
                "CHAT_MEMORY_AND_SCORE_WRITE_NOT_PERFORMED",
                "This chat did not save a memory or change any deterministic score, formula, or evidence. Presentation preferences must be saved explicitly in Personalization and cannot establish business facts or alter scores.",
                "Leave the official score unchanged, resolve its cited evidence gaps through governed records, and save any presentation preference separately in Personalization.",
            )
        if (
            "exchange rate" in query
            or "conversion date" in query
            or "currency conversion" in query
            or " in euro" in query
        ):
            return (
                "UNSUPPORTED_CURRENCY_CONVERSION",
                "No currency conversion was performed. Keep the stored currency unless an approved exchange-rate source and conversion date are available.",
                "Retain the stored currency and obtain an approved exchange-rate source and conversion date before converting or relabeling the amount.",
            )
        if "shared industry keyword" in query or (
            "general" in query
            and "article" in query
            and "award" in query
            and "order" in query
        ):
            return (
                "GENERIC_PUBLIC_MENTION_NOT_CANONICAL_EVIDENCE",
                "A generic article or shared keyword is not canonical account evidence and did not create or publish a customer award, RFQ, opportunity, or internal order. Existing records retain their canonical types.",
                "Leave the customer attachment and order unresolved until source evidence passes canonical identity and publication review.",
            )
        if ("assume" in query or "hypothetical" in query) and (
            "certificate" in query or "certification" in query
        ):
            return (
                "HYPOTHETICAL_QUALIFICATION_NOT_EVIDENCE",
                "The assumed certificate expiry is hypothetical, not verified current certificate evidence. Relationship utility cannot override qualification or delivery-feasibility gates.",
                "Verify the facility-scoped certificate and qualification validity before any commitment; do not rely on relationship utility alone.",
            )
        return None

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
