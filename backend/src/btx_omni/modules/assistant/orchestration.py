"""Bounded Omni POC orchestration over supplied governed read models only."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum

from btx_omni.ai.contracts import ReadIntent
from btx_omni.domain.common import EvidenceState
from btx_omni.domain.markets import primary_market_label
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.modules.scoring.account_attractiveness import (
    seller_attractiveness_projection,
)
from btx_omni.providers.sample.environment import SampleEnvironment


class AssistantProvenance(StrEnum):
    CANONICAL_FACT = "CANONICAL_FACT"
    STORED_INTELLIGENCE = "STORED_INTELLIGENCE"
    DETERMINISTIC_DERIVATION = "DETERMINISTIC_DERIVATION"
    MISSING_UNAVAILABLE = "MISSING_UNAVAILABLE"
    LIVE_PUBLIC_RESEARCH = "LIVE_PUBLIC_RESEARCH"


@dataclass(frozen=True)
class OmniCitation:
    label: str
    url: str


@dataclass(frozen=True)
class OmniResponse:
    content: str
    account_id: str
    citations: tuple[str, ...]
    provenance: tuple[AssistantProvenance, ...]
    missingness: tuple[str, ...]
    recommended_action: str | None
    citation_links: tuple[OmniCitation, ...] = ()
    account_name: str | None = None
    source_of_record: bool = False
    public_research_permitted: bool = False
    context_used: dict[str, object] = field(default_factory=dict)
    conversation_referent: dict[str, object] | None = None
    language_provider: str = "deterministic"
    language_model: str | None = None
    provider_status: str = "NOT_CONFIGURED"
    structured_relationship: dict[str, object] | None = None
    structured_reads: dict[str, object] | None = None
    structured_market: dict[str, object] | None = None
    provider_usage: tuple[dict[str, object], ...] = ()
    run_id: str | None = None


class OmniOrchestrator:
    """No SQL, tools, writes, or source authority: only supplied POC facts."""

    def answer(
        self,
        environment: SampleEnvironment,
        *,
        account_id: str | None,
        question: str,
        observed_at,
        context: dict[str, object] | None = None,
        intelligence_events: Iterable[Mapping[str, object]] | None = None,
        work_items: Iterable[object] = (),
    ) -> OmniResponse:
        """Resolve bounded typed continuation before executing the existing deterministic routes."""
        event_records = (
            tuple(intelligence_events)
            if intelligence_events is not None
            else self._sample_event_records(environment)
        )
        work_records = tuple(work_items)
        resolved_context, conversation_used = self._resolve_conversation_context(
            environment,
            question=question.casefold().strip(),
            context=context or {},
            intelligence_events=event_records,
            work_items=work_records,
        )
        response = self._answer_current(
            environment,
            account_id=account_id,
            question=question,
            observed_at=observed_at,
            context=resolved_context,
            intelligence_events=event_records,
            work_items=work_records,
        )
        return self._attach_conversation_referent(
            environment,
            response=response,
            question=question.casefold().strip(),
            conversation_used=conversation_used,
        )

    def _answer_current(
        self,
        environment: SampleEnvironment,
        *,
        account_id: str | None,
        question: str,
        observed_at,
        context: dict[str, object] | None = None,
        intelligence_events: Iterable[Mapping[str, object]] | None = None,
        work_items: Iterable[object] = (),
    ) -> OmniResponse:
        """Bounded deterministic retrieval fallback; it never presents itself as model output."""
        query = question.casefold().strip()
        accounts = list(environment.accounts)
        product_context = context or {}
        if product_context.get("_conversation_ambiguity"):
            return OmniResponse(
                "I can't determine a unique conversational referent for that follow-up. Select or name a canonical Customer, event, facility, or Action and ask again.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                (
                    "Conversational reference is ambiguous; no canonical entity was selected.",
                ),
                None,
                (),
                None,
            )
        if product_context.get("_conversation_stale"):
            return OmniResponse(
                "The prior conversational referent no longer resolves through the current canonical read model, so Omni will not reconstruct it from assistant text.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Conversational referent is unavailable or stale.",),
                None,
                (),
                None,
            )
        selected_account_id = product_context.get("selected_account_id")
        if (
            isinstance(selected_account_id, str)
            and self._is_account_follow_up_question(query)
            and not self._is_global_cross_account_question(query)
            and not self._is_screen_summary_question(query)
            and not self._is_relationship_question(query)
            and not (
                isinstance(product_context.get("selected_event_id"), str)
                and self._is_event_question(query)
            )
            and not (
                isinstance(product_context.get("selected_facility_id"), str)
                and self._is_facility_question(query)
            )
            and not (
                isinstance(product_context.get("selected_action_id"), str)
                and self._is_action_question(query)
            )
        ):
            return self._account_follow_up_answer(
                environment,
                account_id=selected_account_id,
                question=query,
                observed_at=observed_at,
                work_items=work_items,
                context=product_context,
            )
        cross_intent = self._cross_account_intent(query)
        # A comparison of records inside an explicitly selected account is not
        # automatically a request to compare two companies. Model interpretation
        # remains available; this is the conservative deterministic fallback.
        if (cross_intent == 'COMPARE' and account_id in environment.commercial_ledgers
                and len(self._comparison_accounts_named(query, environment)) < 2
                and re.search(r'\b(quote|quotes|revisions?|delivery|shipments?|revenue|acceptance|history)\b', query)):
            cross_intent = None
        comparison_ids = product_context.get("_conversation_comparison_ids")
        if (
            isinstance(comparison_ids, tuple)
            and len(comparison_ids) == 2
            and self._is_comparison_follow_up(query)
        ):
            return self._comparison_follow_up_answer(
                environment, comparison_ids, query, observed_at, work_items
            )
        if cross_intent:
            event_records = (
                tuple(intelligence_events)
                if intelligence_events is not None
                else self._sample_event_records(environment)
            )
            return self._cross_account_answer(
                environment,
                intent=cross_intent,
                question=query,
                observed_at=observed_at,
                context=product_context,
                intelligence_events=event_records,
                work_items=work_items,
            )
        selected_event_id = product_context.get("selected_event_id")
        if isinstance(selected_event_id, str) and self._is_event_question(query):
            event_records = (
                tuple(intelligence_events)
                if intelligence_events is not None
                else self._sample_event_records(environment)
            )
            return self._selected_event_answer(
                environment,
                event_records=event_records,
                work_items=work_items,
                event_id=selected_event_id,
                question=query,
                observed_at=observed_at,
                context=product_context,
            )
        selected_facility_id = product_context.get("selected_facility_id")
        if isinstance(selected_facility_id, str) and self._is_facility_question(query):
            return self._selected_facility_answer(
                environment,
                facility_id=selected_facility_id,
                question=query,
                observed_at=observed_at,
                context=product_context,
            )
        selected_action_id = product_context.get("selected_action_id")
        if isinstance(selected_action_id, str) and self._is_action_question(query):
            event_records = (
                tuple(intelligence_events)
                if intelligence_events is not None
                else self._sample_event_records(environment)
            )
            return self._selected_action_answer(
                environment,
                work_items=work_items,
                event_records=event_records,
                action_id=selected_action_id,
                question=query,
                context=product_context,
            )
        if self._is_relationship_question(query):
            return self._relationship_answer(
                environment,
                question=query,
                account_id=account_id,
                context=product_context,
            )
        if self._is_screen_summary_question(query):
            event_records = (
                tuple(intelligence_events)
                if intelligence_events is not None
                else self._sample_event_records(environment)
            )
            return self._screen_summary_answer(
                environment,
                question=query,
                observed_at=observed_at,
                context=product_context,
                intelligence_events=event_records,
                work_items=work_items,
            )
        interpreted_intent = product_context.get("_interpreted_intent")
        if isinstance(interpreted_intent, str):
            try:
                intent = ReadIntent(interpreted_intent)
            except ValueError:
                intent = None
            if intent is not None:
                event_records = (
                    tuple(intelligence_events)
                    if intelligence_events is not None
                    else self._sample_event_records(environment)
                )
                return self._interpreted_read_answer(
                    environment,
                    intent=intent,
                    entity_text=product_context.get("_interpreted_entity_text"),
                    account_id=account_id,
                    question=query,
                    observed_at=observed_at,
                    context=product_context,
                    intelligence_events=event_records,
                    work_items=work_items,
                )
        session_account_id = product_context.get("session_account_id")
        session_id = session_account_id if isinstance(session_account_id, str) else None
        account = next(
            (item for item in accounts if item.id == (account_id or session_id)), None
        )
        if account is None:
            named_accounts = self._accounts_named_in(query, environment)
            account = named_accounts[0] if len(named_accounts) == 1 else None
        if account is None:
            return self._unscoped_answer(
                environment, observed_at=observed_at, question=query
            )
        alerts = CommercialAlertEngine().evaluate(
            environment.commercial_contexts,
            environment.quotes,
            observed_at=observed_at,
            orders=environment.orders,
        )
        account_alerts = tuple(item for item in alerts if item.account_id == account.id)
        citations: list[str] = (
            [account.provenance.source_record_id] if account.provenance else []
        )
        citation_links: list[OmniCitation] = []
        if account.provenance and account.provenance.source_url:
            citation_links.append(
                OmniCitation("Public company identity", account.provenance.source_url)
            )
        missing: list[str] = []
        reference_only = account.public_research_state == "SANITIZED_REFERENCE"
        lines = [
            f"Deterministic governed answer for {account.legal_name}. "
            + ("Identity and location come from a sanitized reference source." if reference_only else "Public identity, location, and cited events are publicly verified.")
            + " BTX commercial, CRM, ownership, deal, quote, scoring, and workflow context is simulated POC data when present."
        ]
        public_identity_state = (
            account.public_identity.verification_state.value
            if account.public_identity
            else "UNVERIFIED"
        )
        lines.append(
            f"Public identity: {public_identity_state}; BTX commercial context is simulated and not a connected source record."
        )
        lines.append(f"Canonical industries: {primary_market_label(account.industries)}.")
        if account.btx_top_100:
            lines.append("BTX Top 100: yes, sourced from the sanitized POC Top 100 reference workbook; no rank is inferred.")
        if account.public_relationship:
            lines.append(
                f"Public relationship evidence: {account.public_relationship.state.value} ({account.public_relationship.confidence}); it is not BTX internal confirmation."
            )
            citations.extend(account.public_relationship.provenance.source_ids)
        if account.public_contacts:
            lines.append(
                f"Contact Research: {len(account.public_contacts)} public research record(s), not CRM contacts."
            )
        if account_alerts:
            lines.append(
                "Alerts: " + ", ".join(item.type.value for item in account_alerts) + "."
            )
            citations.extend(
                value for alert in account_alerts for value in alert.evidence_ids
            )
        commercial_contexts = [
            item
            for item in environment.commercial_contexts
            if item.account_id == account_id
        ]
        if not commercial_contexts:
            missing.append("PRISM commercial context unavailable.")
        if (
            "score" in question.casefold() or "attractive" in question.casefold()
        ) and account.id in environment.scoring_inputs:
            score = seller_attractiveness_projection(
                environment.attractiveness_inputs(account.id),
                calculated_at=observed_at,
            )
            lines.append(
                f"Account Attractiveness: {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}."
            )
            missing.extend(score.missingness)
        elif "score" in question.casefold() or "attractive" in question.casefold():
            missing.append(
                "Account Attractiveness is unavailable: no simulated BTX scoring input is mapped to this public identity."
            )
        events = [
            item
            for item in environment.intelligence_events
            if item.account_name == account.legal_name
        ]
        if events:
            normalized = normalize_signal(
                events[0],
                account_name_to_id={
                    item.legal_name: item.id for item in environment.accounts
                },
                provenance=account.provenance,
            )
            lines.append(
                f"Intelligence: {normalized.kind.value}; {normalized.relevance_explanation}"
            )
            citations.extend(normalized.evidence_ids)
            citation_links.append(OmniCitation(normalized.title, normalized.source_url))
            if normalized.evidence_state is not EvidenceState.CONFIRMED:
                missing.append(
                    f"Intelligence evidence is {normalized.evidence_state.value}, not confirmed."
                )
        pairs = [
            (component, quote)
            for component in environment.matching_components
            for quote in environment.matching_quotes
            if component.account_id == account_id and quote.account_id == account_id
        ]
        if pairs:
            match = match_component_to_quote(*pairs[0])
            lines.append(
                f"Commercial matching: {match.method.value} ({match.review_state.value})."
            )
            citations.extend(match.evidence_ids)
        companies = [
            item for item in environment.crm_companies if item.account_id == account.id
        ]
        if not companies:
            missing.append("CRM provider/account context unavailable.")
        else:
            company_ids = {item.id for item in companies}
            contacts = [
                item
                for item in environment.crm_contacts
                if item.company_id in company_ids
            ]
            lines.append(
                f"CRM owner: {companies[0].owner_id}; shared role families: {', '.join(sorted({item.role_family for item in contacts}))}."
            )
            citations.extend(item.provenance.source_record_id for item in companies)
        action = (
            account_alerts[0].recommended_action
            if account_alerts
            else "Review governed commercial context before taking action."
        )
        if "compare" in query:
            peers = [
                item.legal_name
                for item in accounts
                if item.public_identity
                and item.id != account.id
                and item.industries == account.industries
            ][:3]
            lines.append(
                f"Comparable researched {primary_market_label(account.industries)} targets: {', '.join(peers) or 'none loaded'}."
            )
        lines.append(
            "This is a deterministic fallback, not model-generated advice. Omni is read-only and cannot perform CRM writes."
        )
        context_used = {"account_id": account.id}
        if product_context.get("surface"):
            context_used["surface"] = str(product_context["surface"])
        return OmniResponse(
            " ".join(lines),
            account.id,
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)),
            action,
            tuple(dict.fromkeys(citation_links)),
            account.legal_name,
            context_used=context_used,
        )

    @staticmethod
    def _is_event_question(question: str) -> bool:
        return any(
            phrase in question
            for phrase in (
                "what happened",
                "why does this matter",
                "what does this mean",
                "who is this about",
                "what evidence",
                "evidence supports",
                "is this actionable",
                "this award",
                "this event",
                "which account is it tied",
                "what company is it tied",
                "which account is associated",
                "where did this come from",
                "why is this important",
            )
        )

    @staticmethod
    def _is_facility_question(question: str) -> bool:
        return any(
            phrase in question
            for phrase in (
                "this facility",
                "what is this facility",
                "who owns this facility",
                "which account is this facility",
                "what do we know about this location",
                "evidence supports this facility",
                "facility record",
                "btx context for this facility",
                "which account owns it",
                "what account owns it",
            )
        )

    @staticmethod
    def _is_action_question(question: str) -> bool:
        return any(
            phrase in question
            for phrase in (
                "this action",
                "why was this created",
                "why did this action appear",
                "what triggered this",
                "evidence supports this action",
                "review before acting",
                "what account is this for",
                "what should i do next",
                "is this action still valid",
                "what would happen if i act",
                "execute this action",
                "complete this action",
                "go ahead and execute",
                "which account is it for",
                "what evidence supports it",
            )
        )

    @staticmethod
    def _is_relationship_question(question: str) -> bool:
        return any(
            phrase in question
            for phrase in (
                "how are we connected",
                "how are these companies connected",
                "connected",
                "relationship",
                "relationships",
                "warm path",
                "route into",
                "who could introduce",
                "do we know anyone connected",
                "programs connect",
                "companies are related",
                "related?",
                "introduction task",
                "warmer path",
            )
        )

    @staticmethod
    def _is_account_follow_up_question(question: str) -> bool:
        return OmniOrchestrator._account_follow_up_intent(question) is not None

    @staticmethod
    def _account_follow_up_intent(question: str) -> str | None:
        """Classify bounded account continuations without relying on one exact phrase."""
        if re.match(r"^(what|who|where)\s+(is|are)\b", question.casefold()):
            return None
        words = set(re.findall(r"[a-z0-9]+", question.casefold()))
        if words & {"action", "actions", "work", "task", "tasks"}:
            return "ACTIONS"
        if words & {"quote", "quotes", "rfq", "rfqs"}:
            return "QUOTES"
        if (
            words & {"changed", "change", "recent", "recently", "new", "latest", "intelligence", "signal", "signals"}
        ):
            return "INTELLIGENCE"
        if (
            words & {"matter", "matters", "important", "importance", "significant", "significance", "relevant"}
        ):
            return "SIGNIFICANCE"
        if (
            ("next" in words and words & {"do", "step", "move", "action"})
            or ("recommend" in words)
            or ("should" in words and "do" in words)
        ):
            return "NEXT_ACTION"
        if words & {"more", "else", "summary", "overview"} and len(words) <= 10:
            return "SUMMARY"
        return None

    @staticmethod
    def _is_global_cross_account_question(question: str) -> bool:
        return bool(
            re.search(r"\b(which|what)\s+(?:[a-z]+\s+){0,2}(accounts|customers|prospects)\b", question)
        )

    @staticmethod
    def _is_comparison_follow_up(question: str) -> bool:
        return any(
            phrase in question
            for phrase in (
                "which one has the higher score",
                "which one scores higher",
                "which one has more open actions",
                "which has more open actions",
            )
        )

    @staticmethod
    def _is_conversational_follow_up(question: str) -> bool:
        return OmniOrchestrator._is_account_follow_up_question(question) or any(
            phrase in question
            for phrase in (
                "what about it",
                "why does that matter",
                "why is this important",
                "which account is it tied",
                "what company is it tied",
                "which account is associated",
                "where did this come from",
                "which account owns it",
                "what account owns it",
                "which account is it for",
                "what evidence supports it",
                "does it have open actions",
                "does that account have open actions",
                "any intelligence",
                "does it have quote history",
                "does that account have quote history",
                "warmer path",
                "what about the other one",
                "which one has the higher score",
                "which one scores higher",
                "which one has more open actions",
            )
        )

    def _resolve_conversation_context(
        self,
        environment: SampleEnvironment,
        *,
        question: str,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
    ) -> tuple[dict[str, object], dict[str, str]]:
        """Apply explicit > current UI > typed conversation > surface/filter > fallback."""
        resolved = dict(context)
        referent = context.get("conversation_referent")
        if not isinstance(referent, Mapping):
            return resolved, {}
        # Explicit current-turn entity/query families never inherit old entity scope.
        if (
            self._accounts_named_in(question, environment)
            or (
                self._cross_account_intent(question)
                and self._is_global_cross_account_question(question)
                and not self._is_comparison_follow_up(question)
            )
            or self._is_screen_summary_question(question)
            or not self._is_conversational_follow_up(question)
        ):
            return resolved, {}
        used: dict[str, str] = {}
        current_selected = {
            "event_id": resolved.get("selected_event_id"),
            "facility_id": resolved.get("selected_facility_id"),
            "action_id": resolved.get("selected_action_id"),
            "account_id": resolved.get("selected_account_id"),
        }
        # Current UI selection wins when it supplies the same semantic type.
        if isinstance(current_selected["event_id"], str) and self._is_event_question(
            question
        ):
            return resolved, {}
        if isinstance(
            current_selected["facility_id"], str
        ) and self._is_facility_question(question):
            return resolved, {}
        if isinstance(current_selected["action_id"], str) and self._is_action_question(
            question
        ):
            return resolved, {}
        if isinstance(
            current_selected["account_id"], str
        ) and self._is_account_follow_up_question(question):
            return resolved, {}

        account_ids = {account.id for account in environment.accounts}
        event_ids = {
            str(event.get("id"))
            for event in intelligence_events
            if isinstance(event.get("id"), str)
        }
        facility_ids = {facility.id for facility in environment.public_facilities} | {
            facility.id for facility in environment.btx_facilities
        }
        action_ids = {getattr(item, "id", "") for item in work_items}
        event_id = referent.get("event_id")
        facility_id = referent.get("facility_id")
        action_id = referent.get("action_id")
        account_id = referent.get("account_id")
        comparison = referent.get("comparison_account_ids")
        relationship = referent.get("relationship_account_ids")

        if (
            self._is_comparison_follow_up(question)
            and isinstance(comparison, (list, tuple))
            and len(comparison) == 2
            and all(
                isinstance(item, str) and item in account_ids for item in comparison
            )
        ):
            resolved["_conversation_comparison_ids"] = tuple(comparison)
            used["comparison"] = ",".join(comparison)
            return resolved, used
        if "other one" in question:
            if (
                isinstance(comparison, (list, tuple))
                and len(comparison) == 2
                and isinstance(account_id, str)
                and account_id in comparison
            ):
                other = comparison[1] if comparison[0] == account_id else comparison[0]
                resolved["session_account_id"] = other
                used["account_id"] = other
                return resolved, used
            resolved["_conversation_ambiguity"] = True
            return resolved, {}
        if (
            isinstance(event_id, str)
            and event_id in event_ids
            and self._is_event_question(question)
        ):
            resolved["selected_event_id"] = event_id
            used["event_id"] = event_id
            return resolved, used
        if isinstance(event_id, str) and self._is_event_question(question):
            resolved["_conversation_stale"] = True
            return resolved, {}
        if (
            isinstance(facility_id, str)
            and facility_id in facility_ids
            and self._is_facility_question(question)
        ):
            resolved["selected_facility_id"] = facility_id
            used["facility_id"] = facility_id
            return resolved, used
        if isinstance(facility_id, str) and self._is_facility_question(question):
            resolved["_conversation_stale"] = True
            return resolved, {}
        if (
            isinstance(action_id, str)
            and action_id in action_ids
            and self._is_action_question(question)
        ):
            resolved["selected_action_id"] = action_id
            used["action_id"] = action_id
            return resolved, used
        if isinstance(action_id, str) and self._is_action_question(question):
            resolved["_conversation_stale"] = True
            return resolved, {}
        if (
            isinstance(account_id, str)
            and account_id in account_ids
            and self._is_account_follow_up_question(question)
        ):
            resolved["selected_account_id"] = account_id
            used["account_id"] = account_id
            return resolved, used
        if isinstance(account_id, str) and self._is_account_follow_up_question(
            question
        ):
            resolved["_conversation_stale"] = True
            return resolved, {}
        if (
            isinstance(facility_id, str)
            and facility_id in facility_ids
            and "that account" in question
        ):
            facility = next(
                (
                    item
                    for item in environment.public_facilities
                    if item.id == facility_id
                ),
                None,
            )
            if facility and facility.account_id in account_ids:
                resolved["selected_account_id"] = facility.account_id
                used["account_id"] = facility.account_id
                return resolved, used
        if (
            isinstance(relationship, (list, tuple))
            and relationship
            and all(
                isinstance(item, str) and item in account_ids for item in relationship
            )
            and self._is_relationship_question(question)
        ):
            resolved["selected_account_id"] = relationship[0]
            used["account_id"] = relationship[0]
        return resolved, used

    def _attach_conversation_referent(
        self,
        environment: SampleEnvironment,
        *,
        response: OmniResponse,
        question: str,
        conversation_used: Mapping[str, str],
    ) -> OmniResponse:
        """Emit only typed canonical IDs from a successful route; assistant prose is never read."""
        used = dict(response.context_used)
        if (
            conversation_used
            and any(
                used.get(field) == value
                for field, value in conversation_used.items()
                if field != "comparison"
            )
        ) or (
            conversation_used.get("comparison") and used.get("comparison_account_ids")
        ):
            used["context_source"] = "conversation"
        route: str | None = None
        referent: dict[str, object] = {}
        if self._is_screen_summary_question(question) or (
            self._cross_account_intent(question)
            and self._cross_account_intent(question) != "COMPARE"
            and not self._is_comparison_follow_up(question)
            and not conversation_used
        ):
            return replace(response, context_used=used, conversation_referent=None)
        if "event_id" in used:
            event_id = used["event_id"]
            if isinstance(event_id, str):
                referent["event_id"] = event_id
                route = "EVENT"
        if "facility_id" in used:
            facility_id = used["facility_id"]
            if isinstance(facility_id, str):
                referent["facility_id"] = facility_id
                route = "FACILITY"
        if "action_id" in used:
            action_id = used["action_id"]
            if isinstance(action_id, str):
                referent["action_id"] = action_id
                route = "ACTION"
        account_id = used.get("account_id")
        if isinstance(account_id, str) and any(
            account.id == account_id for account in environment.accounts
        ):
            referent["account_id"] = account_id
            route = route or "ACCOUNT"
        related = used.get("related_account_id")
        if isinstance(account_id, str) and isinstance(related, str):
            if self._is_relationship_question(question):
                referent["relationship_account_ids"] = [account_id, related]
                route = "RELATIONSHIP"
            elif self._cross_account_intent(
                question
            ) == "COMPARE" or self._is_comparison_follow_up(question):
                referent.pop("account_id", None)
                referent["comparison_account_ids"] = [account_id, related]
                route = "COMPARISON"
        elif isinstance(account_id, str) and self._is_relationship_question(question):
            referent["relationship_account_ids"] = [account_id]
            route = "RELATIONSHIP"
        if route:
            referent["route"] = route
        return replace(
            response, context_used=used, conversation_referent=referent or None
        )

    def _interpreted_read_answer(
        self,
        environment: SampleEnvironment,
        *,
        intent: ReadIntent,
        entity_text: object,
        account_id: str | None,
        question: str,
        observed_at,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
    ) -> OmniResponse:
        """Execute a validated model intent through existing deterministic read routes."""
        clean_context = {
            key: value
            for key, value in context.items()
            if key not in {"_interpreted_intent", "_interpreted_entity_text"}
        }
        if intent is ReadIntent.SCREEN_SUMMARY:
            return self._screen_summary_answer(
                environment,
                question=question,
                observed_at=observed_at,
                context=clean_context,
                intelligence_events=intelligence_events,
                work_items=work_items,
            )
        if (intent is ReadIntent.GENERAL_OVERVIEW
                and not self._is_global_cross_account_question(question)
                and any(item.id == account_id for item in environment.accounts)):
            # A model's broad intent label cannot discard explicit canonical
            # request scope. Record questions still need the scoped read tools.
            intent = ReadIntent.ACCOUNT_OVERVIEW
        if intent is ReadIntent.GENERAL_OVERVIEW:
            return self._unscoped_answer(
                environment,
                observed_at=observed_at,
                question="summarize the governed portfolio",
            )

        candidates: tuple[object, ...]
        if isinstance(entity_text, str):
            # Provider output may copy entity text, but may not inject a Customer
            # that the user did not name in the current question.
            if not re.search(
                rf"(?<!\w){re.escape(entity_text.casefold())}(?!\w)", question
            ):
                return self._interpreted_entity_clarification(
                    entity_text, ambiguous=False
                )
            if len(self._accounts_named_in(question, environment)) > 1:
                return self._interpreted_entity_clarification(
                    entity_text, ambiguous=True
                )
            candidates = self._accounts_matching_exact_text(entity_text, environment)
            if not candidates and account_id:
                # A word-boundary short name can refer to the explicitly selected
                # account, but is never a global identity alias or a new account.
                selected = next((item for item in environment.accounts if item.id == account_id), None)
                normalized = entity_text.casefold().strip()
                if selected and len(normalized) >= 5 and selected.legal_name.casefold().startswith(normalized + ' '):
                    candidates = (selected,)
            if len(candidates) != 1:
                return self._interpreted_entity_clarification(
                    entity_text, ambiguous=len(candidates) > 1
                )
        else:
            referent = clean_context.get("conversation_referent")
            referent_id = (
                referent.get("account_id") if isinstance(referent, Mapping) else None
            )
            selected_id = next(
                (
                    value
                    for value in (
                        account_id,
                        clean_context.get("selected_account_id"),
                        clean_context.get("session_account_id"),
                        referent_id,
                    )
                    if isinstance(value, str)
                ),
                None,
            )
            candidates = tuple(
                item for item in environment.accounts if item.id == selected_id
            )
            if len(candidates) != 1:
                return self._interpreted_entity_clarification(None, ambiguous=False)

        account = candidates[0]
        if intent is ReadIntent.ACCOUNT_OVERVIEW:
            return self._answer_current(
                environment,
                account_id=account.id,
                question=question,
                observed_at=observed_at,
                context=clean_context,
                intelligence_events=intelligence_events,
                work_items=work_items,
            )
        canonical_questions = {
            ReadIntent.ACCOUNT_INTELLIGENCE: "any intelligence",
            ReadIntent.ACCOUNT_SIGNIFICANCE: "why does that matter",
            ReadIntent.ACCOUNT_NEXT_ACTION: "what should i do next",
            ReadIntent.ACCOUNT_ACTIONS: "does it have open actions",
            ReadIntent.ACCOUNT_QUOTES: "does it have quote history",
        }
        return self._account_follow_up_answer(
            environment,
            account_id=account.id,
            question=canonical_questions[intent],
            observed_at=observed_at,
            work_items=work_items,
            context=clean_context,
        )

    @staticmethod
    def _accounts_matching_exact_text(
        entity_text: str, environment: SampleEnvironment
    ) -> tuple[object, ...]:
        normalized = entity_text.casefold().strip()
        matches: list[object] = []
        for account in environment.accounts:
            names = [account.legal_name]
            if account.public_identity:
                names.extend(field.value for field in account.public_identity.aliases)
            if any(name.casefold().strip() == normalized for name in names):
                matches.append(account)
        return tuple(matches)

    @staticmethod
    def _interpreted_entity_clarification(
        entity_text: str | None, *, ambiguous: bool
    ) -> OmniResponse:
        detail = (
            f"'{entity_text}' matches more than one canonical Customer"
            if ambiguous and entity_text
            else (
                f"'{entity_text}' does not resolve uniquely to a canonical Customer"
                if entity_text
                else "no canonical Customer is selected or named"
            )
        )
        return OmniResponse(
            f"I need clarification because {detail}. Select or name one Customer; Omni will not invent an ID.",
            "",
            (),
            (AssistantProvenance.MISSING_UNAVAILABLE,),
            (f"Model-proposed entity text was not uniquely resolved: {detail}.",),
            None,
            (),
            None,
            context_used={"interpretation_status": "CLARIFICATION"},
        )

    def _account_follow_up_answer(
        self,
        environment: SampleEnvironment,
        *,
        account_id: str,
        question: str,
        observed_at,
        work_items: Iterable[object],
        context: Mapping[str, object],
    ) -> OmniResponse:
        account = next(
            (item for item in environment.accounts if item.id == account_id), None
        )
        context_used: dict[str, object] = {"account_id": account_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if account is None:
            return OmniResponse(
                "I can't resolve the account referent to a current canonical account. I will not reconstruct it from earlier assistant text.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Conversational account referent is unavailable or stale.",),
                None,
                (),
                None,
                context_used=context_used,
            )
        lines = [f"Canonical account follow-up for {account.legal_name}."]
        citations: list[str] = []
        missing: list[str] = []
        intent = self._account_follow_up_intent(question)
        if intent == "ACTIONS":
            items = [
                item
                for item in self._open_work_items(work_items)
                if getattr(item, "account_id", None) == account.id
            ]
            if items:
                lines.append(
                    f"Current open governed work items: {len(items)}; highest existing priority is {min(items, key=self._work_sort_key).priority}."
                )
                citations.extend(
                    value
                    for item in items
                    for value in getattr(item, "evidence_ids", ())
                )
            else:
                lines.append(
                    "No open governed work items are present for this account in the current session."
                )
            lines.append(
                "Workflow facts are current session-only SAMPLE state; Omni is read-only."
            )
        elif intent == "INTELLIGENCE":
            events = [
                event
                for event in self._sample_event_records(environment)
                if event.get("account_id") == account.id
            ]
            if events:
                latest = max(events, key=self._event_sort_key)
                lines.append(
                    f"Canonical source-backed Intelligence: {latest.get('title') or latest.get('id')}; evidence {latest.get('evidence_state') or 'MISSING'}."
                )
                citations.extend(str(value) for value in latest.get("evidence_ids", ()))
            else:
                lines.append(
                    "No canonical Intelligence event is currently associated with this account."
                )
            lines.append(
                "No event geography or account association is inferred beyond the canonical Monitor read."
            )
        elif intent == "QUOTES":
            quotes = [
                quote for quote in environment.quotes if quote.account_id == account.id
            ]
            lines.append(f"Canonical quote-history records: {len(quotes)}.")
            lines.append(
                "Quote history is current SAMPLE commercial context; Omni does not infer capability or production truth from it."
            )
        elif intent == "SIGNIFICANCE":
            alerts = tuple(
                item
                for item in CommercialAlertEngine().evaluate(
                    environment.commercial_contexts,
                    environment.quotes,
                    observed_at=observed_at,
                    orders=environment.orders,
                )
                if item.account_id == account.id
            )
            if account.prospect_rationale:
                lines.append(f"Governed rationale: {account.prospect_rationale}")
            if alerts:
                lines.append(f"Current SAMPLE commercial attention: {alerts[0].trigger_reason}")
                citations.extend(alerts[0].evidence_ids)
            if not account.prospect_rationale and not alerts:
                lines.append("No narrower governed significance rationale is available for this Customer.")
                missing.append("Customer significance needs research or governed commercial context.")
            lines.append("Public/reference identity and SAMPLE BTX commercial context remain separate truth categories.")
        elif intent == "NEXT_ACTION":
            alerts = tuple(
                item
                for item in CommercialAlertEngine().evaluate(
                    environment.commercial_contexts,
                    environment.quotes,
                    observed_at=observed_at,
                    orders=environment.orders,
                )
                if item.account_id == account.id
            )
            suggestion = (
                alerts[0].recommended_action
                if alerts
                else account.prospect_rationale
                or "Review governed Customer evidence before choosing an outreach step."
            )
            lines.append(f"Suggested next move: {suggestion}")
            citations.extend(value for item in alerts[:1] for value in item.evidence_ids)
            lines.append("This is read-only guidance; create or update work only in the authorized Actions workflow.")
        else:
            lines.append(f"Canonical industries: {primary_market_label(account.industries)}.")
            lines.append(
                "Ask about recent Intelligence, significance, quotes, or governed Actions for a narrower answer."
            )
        return OmniResponse(
            " ".join(lines),
            account.id,
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(missing),
            None,
            (),
            account.legal_name,
            context_used=context_used,
        )

    def _comparison_follow_up_answer(
        self,
        environment: SampleEnvironment,
        account_ids: tuple[str, str],
        question: str,
        observed_at,
        work_items: Iterable[object],
    ) -> OmniResponse:
        accounts = tuple(
            next(
                (
                    account
                    for account in environment.accounts
                    if account.id == account_id
                ),
                None,
            )
            for account_id in account_ids
        )
        if any(account is None for account in accounts):
            return OmniResponse(
                "I can't resolve both canonical accounts from the stored comparison referent, so I won't recreate the pair from prior prose.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Comparison referent is unavailable or stale.",),
                None,
                (),
                None,
            )
        first, second = accounts
        assert first is not None and second is not None
        context_used = {
            "account_id": first.id,
            "related_account_id": second.id,
            "comparison_account_ids": [first.id, second.id],
        }
        if "score" in question:
            scores = {
                account.id: seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
                    calculated_at=observed_at,
                ).score
                if account.id in environment.scoring_inputs
                else None
                for account in (first, second)
            }
            if None in scores.values():
                return OmniResponse(
                    "One or both accounts lack an available canonical attractiveness score, so Omni cannot compare that dimension.",
                    "",
                    (),
                    (
                        AssistantProvenance.CANONICAL_FACT,
                        AssistantProvenance.MISSING_UNAVAILABLE,
                    ),
                    ("A comparison account has no canonical score.",),
                    None,
                    (),
                    None,
                    context_used=context_used,
                )
            if scores[first.id] == scores[second.id]:
                content = f"For the existing attractiveness-score dimension, {first.legal_name} and {second.legal_name} are tied at {scores[first.id]}."
            else:
                winner = first if scores[first.id] > scores[second.id] else second
                content = f"For the existing attractiveness-score dimension only, {winner.legal_name} is higher: {first.legal_name} {scores[first.id]}; {second.legal_name} {scores[second.id]}."
            return OmniResponse(
                content
                + " Scores use current SAMPLE commercial inputs; Omni did not create a combined priority metric.",
                "",
                (),
                (
                    AssistantProvenance.CANONICAL_FACT,
                    AssistantProvenance.DETERMINISTIC_DERIVATION,
                ),
                (),
                None,
                (),
                None,
                context_used=context_used,
            )
        counts = {
            account.id: len(
                [
                    item
                    for item in self._open_work_items(work_items)
                    if getattr(item, "account_id", None) == account.id
                ]
            )
            for account in (first, second)
        }
        if counts[first.id] == counts[second.id]:
            content = f"Both compared accounts have {counts[first.id]} open governed work item(s) in the current session."
        else:
            winner = first if counts[first.id] > counts[second.id] else second
            content = f"{winner.legal_name} has more open governed work items: {first.legal_name} {counts[first.id]}; {second.legal_name} {counts[second.id]}."
        return OmniResponse(
            content
            + " This is a read-only count of session-only SAMPLE workflow state, not a priority score.",
            "",
            (),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            ),
            (),
            None,
            (),
            None,
            context_used=context_used,
        )

    @staticmethod
    def _is_screen_summary_question(question: str) -> bool:
        """Only explicit page/view phrasing opts into current-screen scope."""
        return any(
            phrase in question
            for phrase in (
                "what matters most on this page",
                "what should i pay attention to here",
                "summarize this screen",
                "what are the most important things here",
                "what should i focus on",
                "key takeaways from this page",
                "summarize this page",
                "highlights from this view",
                "what should i know from this screen",
                "what am i looking at",
                "what monitor context is active",
            )
        )

    @staticmethod
    def _cross_account_intent(question: str) -> str | None:
        """Recognize a deliberately small family of deterministic multi-account reads."""
        has_intelligence = any(
            phrase in question
            for phrase in (
                "recent intelligence",
                "intelligence events",
                "have intelligence",
                "external signals",
                "new external signals",
                "relevant intelligence",
            )
        )
        has_actions = any(
            phrase in question
            for phrase in (
                "open actions",
                "open action",
                "work waiting",
                "pending work item",
                "pending seller work",
                "open seller actions",
                "signals and actions",
            )
        )
        if has_intelligence and has_actions:
            return "INTELLIGENCE_OPEN_ACTIONS"
        if (
            question.startswith("compare ")
            or "which has the higher attractiveness score" in question
            or "which has the higher score" in question
        ):
            return "COMPARE"
        if any(
            phrase in question
            for phrase in (
                "highest scores",
                "top accounts by attractiveness",
                "prospects score highest",
                "strongest attractiveness score",
                "top scored accounts",
                "highest attractiveness",
                "highest score",
                "strongest score",
            )
        ):
            return "SCORE_RANKING"
        if has_actions:
            return "OPEN_ACTIONS"
        if has_intelligence:
            return "INTELLIGENCE"
        if any(
            phrase in question
            for phrase in ("open quote", "quote history", "rfq activity")
        ):
            return "QUOTES"
        return None

    @staticmethod
    def _accounts_named_in(
        question: str, environment: SampleEnvironment
    ) -> tuple[object, ...]:
        """Exact legal-name or researched-alias matching only; no fuzzy entity resolution."""
        matches: list[object] = []
        for account in environment.accounts:
            names = [account.legal_name]
            if account.public_identity:
                names.extend(field.value for field in account.public_identity.aliases)
            if any(
                re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", question)
                for name in names
            ):
                matches.append(account)
        return tuple(matches)

    @staticmethod
    def _unresolved_pair_entity(
        question: str, environment: SampleEnvironment
    ) -> str | None:
        """Name only an exact unresolved member of the common two-account form."""
        match = re.search(r"how are (.+?) and (.+?) connected", question)
        if not match:
            return None
        known = {account.legal_name.casefold() for account in environment.accounts}
        known.update(
            field.value.casefold()
            for account in environment.accounts
            for field in (
                account.public_identity.aliases if account.public_identity else ()
            )
        )
        return next(
            (name for name in match.groups() if name.casefold().strip() not in known),
            None,
        )

    def _relationship_answer(
        self,
        environment: SampleEnvironment,
        *,
        question: str,
        account_id: str | None,
        context: Mapping[str, object],
    ) -> OmniResponse:
        """Adapt canonical relationship paths for Omni without implementing traversal."""
        named = self._accounts_named_in(question, environment)
        unresolved_entity = self._unresolved_pair_entity(question, environment)
        selected_id = context.get("selected_account_id")
        selected = (
            next(
                (item for item in environment.accounts if item.id == selected_id), None
            )
            if isinstance(selected_id, str)
            else None
        )
        explicit = (
            next((item for item in environment.accounts if item.id == account_id), None)
            if account_id
            else None
        )
        source = named[0] if named else explicit or selected
        target = (
            named[1]
            if len(named) > 1
            else (
                named[0]
                if named
                and (explicit or selected)
                and named[0].id != (explicit or selected).id
                else None
            )
        )
        if (
            named
            and len(named) == 1
            and (explicit or selected)
            and named[0].id != (explicit or selected).id
        ):
            source = explicit or selected
            target = named[0]
        context_used: dict[str, object] = {}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if source is None:
            return OmniResponse(
                "I need a canonical researched account to inspect relationship intelligence. Select an account or name one exactly; Omni will not infer a graph node from similarity.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                (
                    "No canonical account was supplied or resolved for the relationship query.",
                ),
                None,
                (),
                None,
                context_used=context_used,
            )
        if unresolved_entity:
            return OmniResponse(
                f"I can't resolve '{unresolved_entity}' to a canonical researched account for this relationship query. I will not fuzzy-match it to a graph node.",
                source.id,
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                (
                    f"Canonical researched account '{unresolved_entity}' was not resolved.",
                ),
                None,
                (),
                source.legal_name,
                context_used=context_used,
            )
        context_used["account_id"] = source.id
        if target is not None:
            context_used["related_account_id"] = target.id
        service = RelationshipIntelligenceService(environment)
        result = service.account_relationships(source.id, depth=4, max_paths=80)
        paths = list(result["paths"])
        if target is not None:
            paths = [
                path
                for path in paths
                if path["target_entity"].kind == "account"
                and path["target_entity"].id == target.id
            ]
        warm_path = any(
            phrase in question
            for phrase in (
                "warm path",
                "route into",
                "who could introduce",
                "introduction task",
            )
        )
        program_query = "programs connect" in question
        contact_query = "do we know anyone connected" in question
        if warm_path:
            customer_ids = {item.account_id for item in environment.commercial_contexts}
            paths = [
                path
                for path in paths
                if path["target_entity"].kind == "account"
                and path["target_entity"].id in customer_ids
                and path["target_entity"].id != source.id
            ]
        elif contact_query:
            paths = [path for path in paths if path["target_entity"].kind == "contact"]
        elif program_query:
            paths = [
                path
                for path in paths
                if any(
                    hop.relationship_type
                    in {
                        "SHARED_PROGRAM",
                        "SHARED_PROGRAM_REVERSE",
                        "PARTICIPATES_IN",
                        "HAS_PARTICIPANT",
                    }
                    for hop in path["hops"]
                )
            ]
        else:
            direct = result["direct_relationships"] if target is None else paths
            paths = list(direct)
        if not paths:
            pair = (
                f" between {source.legal_name} and {target.legal_name}"
                if target
                else f" around {source.legal_name}"
            )
            return OmniResponse(
                f"I don't have an evidence-backed relationship path{pair} in the current canonical graph. That does not establish that no real-world relationship exists.",
                source.id,
                (),
                (
                    AssistantProvenance.CANONICAL_FACT,
                    AssistantProvenance.MISSING_UNAVAILABLE,
                ),
                (
                    "No canonical relationship path was found within the supported traversal depth.",
                ),
                None,
                (),
                source.legal_name,
                context_used=context_used,
            )
        paths.sort(
            key=lambda path: (
                0 if any(not hop.derived for hop in path["hops"]) else 1,
                0 if path["presentation_state"] == "validated" else 1,
                len(path["hops"]),
                path["path_id"],
            )
        )
        selected_paths = paths[:1] if warm_path else paths[:3]
        citations: list[str] = []
        citation_links: list[OmniCitation] = []
        missing: list[str] = []
        lines: list[str] = []
        for path in selected_paths:
            hops = path["hops"]
            rendered = " -> ".join(
                f"{hop.from_entity.name} --{hop.relationship_type}--> {hop.to_entity.name}"
                for hop in hops
            )
            state = path["presentation_state"]
            evidence = path["overall_evidence_state"].value
            lines.append(
                f"Canonical relationship path ({state}; evidence {evidence}): {rendered}."
            )
            if path["narrative"]:
                lines.append(f"Relationship record: {path['narrative']}")
            source_ids = tuple(
                source_id for hop in hops for source_id in hop.source_ids
            )
            if source_ids:
                citations.extend(source_ids)
                lines.append(f"Relationship source IDs: {', '.join(source_ids)}.")
            if state == "needs_validation":
                missing.append(
                    "This relationship path needs validation; a material edge is inferred or lacks attached source IDs."
                )
            if state == "unusable":
                missing.append(
                    "This relationship path has missing or conflicting evidence and is not usable for seller action."
                )
            if not source_ids and any(not hop.derived for hop in hops):
                missing.append(
                    "An explicit relationship edge in this path has no attached relationship source IDs."
                )
            if any(
                hop.relationship_type.startswith("GEOGRAPHIC_CLUSTER") for hop in hops
            ):
                lines.append(
                    "GEOGRAPHIC_CLUSTER is a geographic grouping only; it is not ownership, a commercial relationship, or an introduction route."
                )
            if any(hop.provenance and hop.provenance.synthetic for hop in hops):
                lines.append(
                    "This path includes current SAMPLE commercial or CRM context; it is not connected BTX production data."
                )
        if program_query:
            program_ids = self._program_ids_for_relationship_paths(
                environment, selected_paths
            )
            programs = [item for item in environment.programs if item.id in program_ids]
            if programs:
                lines.append(
                    "Canonical programs on the selected direct relationship record: "
                    + ", ".join(f"{item.name} ({item.id})" for item in programs)
                    + "."
                )
            else:
                missing.append(
                    "The selected relationship paths do not identify a canonical program."
                )
        if warm_path:
            candidate = selected_paths[0]["target_entity"]
            if selected_paths[0]["presentation_state"] == "validated":
                lines.append(
                    f"{candidate.name} has current SAMPLE commercial context. This is a relationship path worth reviewing, not a guaranteed introduction."
                )
            else:
                lines.append(
                    f"{candidate.name} is only a potential route worth validating; the path is not a proven introduction."
                )
        if contact_query and selected_paths:
            contact = next(
                (
                    item
                    for item in environment.crm_contacts
                    if item.id == selected_paths[0]["target_entity"].id
                ),
                None,
            )
            if contact:
                name = (
                    " ".join(
                        value
                        for value in (
                            contact.properties.get("firstname"),
                            contact.properties.get("lastname"),
                        )
                        if value
                    )
                    or contact.role_family
                )
                lines.append(
                    f"The path reaches {name} ({contact.role_family}) in the current SAMPLE CRM dataset. This is not a verified live introduction."
                )
        if any(
            phrase in question
            for phrase in (
                "introduction task",
                "create an introduction",
                "introduce us",
            )
        ):
            lines.append(
                "Omni is read-only and did not create an introduction task, contact, relationship edge, or CRM record."
            )
        lines.append(
            "Relationship evidence remains distinct from account similarity, market overlap, score, and proximity. Omni is read-only and does not validate or modify relationship evidence."
        )
        provenance = [AssistantProvenance.CANONICAL_FACT]
        if any(
            hop.provenance and hop.provenance.synthetic
            for path in selected_paths
            for hop in path["hops"]
        ):
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines),
            source.id,
            tuple(dict.fromkeys(citations)),
            tuple(provenance),
            tuple(dict.fromkeys(missing)),
            None,
            tuple(dict.fromkeys(citation_links)),
            source.legal_name,
            context_used=context_used,
        )

    @staticmethod
    def _program_ids_for_relationship_paths(
        environment: SampleEnvironment, paths: Iterable[Mapping[str, object]]
    ) -> set[str]:
        """Recover only direct-edge program metadata; traversal stays in the relationship service."""
        ids: set[str] = set()
        for path in paths:
            for hop in path["hops"]:
                for edge in environment.relationship_edges:
                    direct = (
                        edge.from_account_id == hop.from_entity.id
                        and edge.to_account_id == hop.to_entity.id
                        and edge.edge_type == hop.relationship_type
                    )
                    reverse = (
                        edge.from_account_id == hop.to_entity.id
                        and edge.to_account_id == hop.from_entity.id
                        and f"{edge.edge_type}_REVERSE" == hop.relationship_type
                    )
                    if (direct or reverse) and edge.program_id:
                        ids.add(edge.program_id)
        return ids

    def _selected_action_answer(
        self,
        environment: SampleEnvironment,
        *,
        work_items: Iterable[object],
        event_records: Iterable[Mapping[str, object]],
        action_id: str,
        question: str,
        context: Mapping[str, object],
    ) -> OmniResponse:
        """Explain one stored governed work item without changing workflow state."""
        item = next(
            (
                candidate
                for candidate in work_items
                if getattr(candidate, "id", None) == action_id
            ),
            None,
        )
        context_used: dict[str, object] = {"action_id": action_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if item is None:
            return OmniResponse(
                "I can't resolve the selected action to a current durable Action. It may have been removed or be outside the current view, but I will not match it by title or Customer.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Selected Action is unavailable in the current authorized view.",),
                None,
                (),
                None,
                context_used=context_used,
            )

        account_id = getattr(item, "account_id", None)
        account = next(
            (
                candidate
                for candidate in environment.accounts
                if candidate.id == account_id
            ),
            None,
        )
        evidence_ids = tuple(getattr(item, "evidence_ids", ()))
        linked_events = [
            event
            for event in event_records
            if {str(value) for value in event.get("evidence_ids", ())}
            & set(evidence_ids)
        ]
        citations = list(evidence_ids)
        citation_links = [
            OmniCitation(
                str(event.get("title") or "Intelligence event"),
                str(event["source_url"]),
            )
            for event in linked_events
            if isinstance(event.get("source_url"), str)
        ]
        missing: list[str] = []
        status = getattr(item, "status", "UNAVAILABLE")
        status_value = getattr(status, "value", str(status))
        priority = getattr(item, "priority", "UNAVAILABLE")
        created_at = getattr(item, "created_at", None)
        created_text = (
            created_at.isoformat()
            if hasattr(created_at, "isoformat")
            else "unavailable"
        )
        lines = [
            f"Canonical governed work item: {getattr(item, 'summary', 'Untitled action')} ({getattr(item, 'id', action_id)}).",
            f"Current status: {status_value}; priority: {priority}; created: {created_text}.",
            "This durable Action is read-only to Omni; SAMPLE evidence remains explicitly labeled.",
        ]
        owner_id = getattr(item, "owner_id", None)
        due_date = getattr(item, "due_date", None)
        if owner_id:
            lines.append(f"Stored owner: {owner_id}.")
        if due_date:
            lines.append(f"Stored due date: {due_date}.")
        notes = getattr(item, "notes", None)
        if notes:
            lines.append(f"Stored workflow note: {notes}")
        if account is None:
            lines.append(
                "No canonical researched account association is available for this work item."
            )
            missing.append(
                "No canonical researched account association is available for this work item."
            )
        else:
            context_used["account_id"] = account.id
            lines.append(f"Canonical account: {account.legal_name} ({account.id}).")
            selected_account_id = context.get("selected_account_id")
            if (
                isinstance(selected_account_id, str)
                and selected_account_id != account.id
            ):
                lines.append(
                    "The UI-selected account does not match this work item's canonical account; action facts use the governed work-item association."
                )
                missing.append(
                    "Selected account context conflicts with the work item's canonical account."
                )
        if evidence_ids:
            lines.append(f"Stored supporting evidence IDs: {', '.join(evidence_ids)}.")
        else:
            missing.append("No evidence IDs are attached to this work item.")
        if linked_events:
            for event in linked_events:
                title = str(event.get("title") or "Intelligence event")
                state = str(event.get("evidence_state") or "MISSING")
                lines.append(
                    f"Exactly linked canonical Intelligence evidence: {title}; evidence state: {state}."
                )
                if state != EvidenceState.CONFIRMED.value:
                    missing.append(
                        f"Linked Intelligence evidence is {state}, not confirmed."
                    )
        else:
            lines.append(
                "No canonical originating Intelligence event is attached to this work item."
            )
            missing.append(
                "No canonical originating Intelligence event is attached to this work item."
            )
        lines.append(
            "No canonical originating commercial-alert or rule ID is stored on this work item, so Omni does not recreate a triggering rule from its summary or account data."
        )
        missing.append(
            "No canonical originating commercial-alert or rule ID is attached to this work item."
        )

        is_execution_request = any(
            phrase in question
            for phrase in ("execute", "complete", "go ahead", "do this for me")
        )
        is_validity_question = "still valid" in question
        if is_validity_question:
            lines.append(
                f"The governed record is currently {status_value}; Omni can report this stored state and evidence, but cannot independently certify continued validity beyond the current session data."
            )
        if is_execution_request:
            lines.append(
                "Omni is read-only and did not execute, complete, dismiss, or update this work item. Existing CRM execution remains separately gated by explicit human confirmation."
            )
        elif "what would happen if i act" in question:
            lines.append(
                "Omni cannot simulate or execute a workflow transition. The current governed state is reported above; any external CRM execution remains separately gated by explicit human confirmation."
            )
        elif "review before acting" in question:
            lines.append(
                "Before acting, review the stored summary and evidence IDs above, any linked canonical Intelligence evidence, and the listed missing or conflicting evidence. No additional checklist is inferred."
            )
        elif "what should i do next" in question:
            lines.append(
                f"The stored governed next step is the work-item summary: {getattr(item, 'summary', 'unavailable')}. No stronger recommendation is generated by Omni."
            )
        lines.append(
            "Any commercial/workflow facts in this response are from the current SAMPLE commercial dataset. Public Intelligence evidence remains source-backed. Omni is read-only and cannot perform CRM writes."
        )
        provenance = [AssistantProvenance.CANONICAL_FACT]
        if linked_events:
            provenance.append(AssistantProvenance.STORED_INTELLIGENCE)
        if account is not None:
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines),
            account.id if account else "",
            tuple(dict.fromkeys(citations)),
            tuple(provenance),
            tuple(dict.fromkeys(missing)),
            getattr(item, "summary", None),
            tuple(dict.fromkeys(citation_links)),
            account.legal_name if account else None,
            context_used=context_used,
        )

    def _selected_facility_answer(
        self,
        environment: SampleEnvironment,
        *,
        facility_id: str,
        question: str,
        observed_at,
        context: Mapping[str, object],
    ) -> OmniResponse:
        """Explain one exact canonical facility without geographic inference."""
        researched = next(
            (item for item in environment.public_facilities if item.id == facility_id),
            None,
        )
        btx = next(
            (item for item in environment.btx_facilities if item.id == facility_id),
            None,
        )
        context_used: dict[str, object] = {"facility_id": facility_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if researched is None and btx is None:
            return OmniResponse(
                "I can't resolve the selected facility to a canonical facility record in the current dataset. I will not match it by name, coordinates, or proximity.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Selected facility is unavailable or stale.",),
                None,
                (),
                None,
                context_used=context_used,
            )

        if btx is not None:
            return self._selected_btx_facility_answer(
                environment,
                facility=btx,
                context_used=context_used,
            )
        assert researched is not None
        return self._selected_researched_facility_answer(
            environment,
            facility=researched,
            question=question,
            observed_at=observed_at,
            context=context,
            context_used=context_used,
        )

    @staticmethod
    def _location_text(facility) -> str:
        return f"{facility.city}, {facility.region}, {facility.country}; canonical coordinates {facility.latitude}, {facility.longitude}"

    def _selected_researched_facility_answer(
        self,
        environment: SampleEnvironment,
        *,
        facility,
        question: str,
        observed_at,
        context: Mapping[str, object],
        context_used: dict[str, object],
    ) -> OmniResponse:
        account = next(
            (item for item in environment.accounts if item.id == facility.account_id),
            None,
        )
        citations = list(facility.provenance.source_ids if facility.provenance else ())
        citation_links = (
            [OmniCitation(facility.name, facility.source_url)]
            if facility.source_url
            else []
        )
        missing: list[str] = []
        lines = [
            f"Canonical researched facility: {facility.name} ({facility.id}). ",
            f"Facility type: {facility.facility_type}. Location: {self._location_text(facility)}.",
            f"Verification state: {facility.verification_state}; source type: {facility.source_type or 'unavailable'}.",
        ]
        if facility.source_url:
            lines.append(
                "The facility's researched public source is cited with this response."
            )
        else:
            missing.append(
                "No source URL is present for this canonical facility record."
            )
        if account is None:
            lines.append(
                "This facility is present in the canonical researched-facility dataset, but no canonical researched account association is established for it here."
            )
            missing.append(
                "No canonical parent account is associated with this facility."
            )
        else:
            lines.append(
                f"Canonical parent account: {account.legal_name} ({account.id})."
            )
            selected_account_id = context.get("selected_account_id")
            if (
                isinstance(selected_account_id, str)
                and selected_account_id != account.id
            ):
                lines.append(
                    "The UI-selected account does not match this facility's canonical parent account; facility facts use the canonical facility association."
                )
                missing.append(
                    "Selected account context conflicts with the facility's canonical parent account."
                )

        action: str | None = None
        if account is not None and "matter" in question:
            context_used["account_id"] = account.id
            score = None
            if account.id in environment.scoring_inputs:
                score = seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
                    calculated_at=observed_at,
                )
                lines.append(
                    f"This facility has no separate facility score. Its parent account's deterministic attractiveness is {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}."
                )
                missing.extend(score.missingness)
            else:
                missing.append(
                    "No canonical account-attractiveness input is mapped to this facility's parent account."
                )
            alerts = CommercialAlertEngine().evaluate(
                environment.commercial_contexts,
                environment.quotes,
                observed_at=observed_at,
                orders=environment.orders,
            )
            account_alerts = [item for item in alerts if item.account_id == account.id]
            if account_alerts:
                action = account_alerts[0].recommended_action
                lines.append(
                    f"In the current SAMPLE commercial dataset, the parent account has a governed alert recommending: {action}"
                )
            else:
                lines.append(
                    "No governed commercial alert currently connects this parent account to a seller recommendation."
                )
        lines.append(
            "This describes the canonical facility record only. Geographic proximity is not used to infer ownership, relationships, or commercial importance. Any commercial context above is from the current SAMPLE commercial dataset; Omni is read-only."
        )
        provenance = [AssistantProvenance.CANONICAL_FACT]
        if action or "account_id" in context_used:
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines),
            account.id if account else "",
            tuple(dict.fromkeys(citations)),
            tuple(provenance),
            tuple(dict.fromkeys(missing)),
            action,
            tuple(dict.fromkeys(citation_links)),
            account.legal_name if account else None,
            context_used=context_used,
        )

    def _selected_btx_facility_answer(
        self,
        environment: SampleEnvironment,
        *,
        facility,
        context_used: dict[str, object],
    ) -> OmniResponse:
        business_unit = next(
            (
                item
                for item in environment.business_units
                if item.id == facility.business_unit_id
            ),
            None,
        )
        citations = [facility.provenance.source_record_id]
        citation_links = (
            [OmniCitation(facility.name, facility.source_url)]
            if facility.source_url
            else []
        )
        missing: list[str] = []
        lines = [
            f"Canonical BTX facility: {facility.name} ({facility.id}). Location: {self._location_text(facility)}.",
            f"Verification state: {facility.verification_state}; source type: {facility.source_type or 'unavailable'}.",
        ]
        if facility.source_url:
            lines.append(
                "The facility's public BTX business-unit source is cited with this response."
            )
        else:
            missing.append(
                "No source URL is present for this canonical BTX facility record."
            )
        if business_unit is None:
            lines.append(
                "No canonical BTX business-unit association is present for this facility."
            )
            missing.append(
                "No canonical BTX business-unit association is present for this facility."
            )
        else:
            lines.append(
                f"Canonical BTX business unit: {business_unit.name} ({business_unit.id})."
            )
            if business_unit.processes:
                lines.append(
                    f"Publicly documented processes: {', '.join(business_unit.processes)}."
                )
        lines.append(
            "This is a public BTX business-unit facility profile, not a production-capacity or prospect/customer record. No customer or prospect account association is inferred. Geographic proximity is not used to infer relationships or commercial importance."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (AssistantProvenance.CANONICAL_FACT,)
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)),
            None,
            tuple(dict.fromkeys(citation_links)),
            None,
            context_used=context_used,
        )

    @staticmethod
    def _sample_event_records(
        environment: SampleEnvironment,
    ) -> tuple[dict[str, object], ...]:
        accounts = {item.id: item for item in environment.accounts}
        names = {item.legal_name: item.id for item in environment.accounts}
        records: list[dict[str, object]] = []
        for raw in environment.intelligence_events:
            provenance = (
                accounts[names[raw.account_name]].provenance
                if raw.account_name in names
                else next(iter(accounts.values())).provenance
            )
            signal = normalize_signal(
                raw, account_name_to_id=names, provenance=provenance
            )
            records.append(
                {
                    "id": signal.id,
                    "kind": signal.kind.value,
                    "title": signal.title,
                    "source_url": signal.source_url,
                    "account_id": signal.account_id,
                    "program_name": signal.program_name,
                    "program_id": None,
                    "facility_id": None,
                    "evidence_state": signal.evidence_state.value,
                    "resolution_state": "RESOLVED"
                    if signal.account_id
                    else "UNRESOLVED",
                    "data_mode": "CURATED_PUBLIC",
                    "observed_at": signal.occurred_at,
                    "relevance_explanation": signal.relevance_explanation,
                    "evidence_ids": signal.evidence_ids,
                    "source_tier": "CURATED_POC_PUBLIC",
                    "provenance": signal.provenance,
                }
            )
        return tuple(records)

    def _selected_event_answer(
        self,
        environment: SampleEnvironment,
        *,
        event_records: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
        event_id: str,
        question: str,
        observed_at,
        context: Mapping[str, object],
    ) -> OmniResponse:
        event = next(
            (record for record in event_records if record.get("id") == event_id), None
        )
        context_used: dict[str, object] = {"event_id": event_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if event is None:
            return OmniResponse(
                "The selected Intelligence event is not available in the current canonical Monitor read model. I cannot explain it or connect it to account history without a canonical event record.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Selected Intelligence event is unavailable or stale.",),
                None,
                (),
                None,
                context_used=context_used,
            )

        account_id = (
            event.get("account_id")
            if isinstance(event.get("account_id"), str)
            else None
        )
        account = next(
            (item for item in environment.accounts if item.id == account_id), None
        )
        title = str(event.get("title") or "Untitled intelligence event")
        kind = str(event.get("kind") or "INTELLIGENCE_EVENT")
        source_url = (
            event.get("source_url")
            if isinstance(event.get("source_url"), str)
            else None
        )
        observed_at_value = event.get("observed_at")
        observed_text = (
            observed_at_value.isoformat()
            if hasattr(observed_at_value, "isoformat")
            else str(observed_at_value or "unavailable")
        )
        evidence_state = str(event.get("evidence_state") or "MISSING")
        resolution_state = str(
            event.get("resolution_state") or ("RESOLVED" if account else "UNRESOLVED")
        )
        citations = [str(value) for value in event.get("evidence_ids", ())]
        citation_links = [OmniCitation(title, source_url)] if source_url else []
        missing: list[str] = []
        lines = [
            f"Source-backed Intelligence event: {title}. Type: {kind}. Observed/source date: {observed_text}."
        ]
        if source_url:
            lines.append("The supplied public source is cited with this response.")
        lines.append(
            f"Evidence state: {evidence_state}; canonical resolution state: {resolution_state}."
        )
        relevance = event.get("relevance_explanation")
        if relevance:
            lines.append(
                f"Seller relevance from the canonical Monitor projection: {relevance}"
            )
        if account is None:
            lines.append(
                "This event is currently unresolved to a canonical researched account, so it cannot be reliably connected to BTX account history, scoring, or workflow context."
            )
            missing.append("No canonical account resolution is present for this event.")
        else:
            context_used["account_id"] = account.id
            lines.append(
                f"Resolved organization: {account.legal_name} ({primary_market_label(account.industries)})."
            )
        program_id = (
            event.get("program_id")
            if isinstance(event.get("program_id"), str)
            else None
        )
        program_name = (
            event.get("program_name")
            if isinstance(event.get("program_name"), str)
            else None
        )
        program = next(
            (item for item in environment.programs if item.id == program_id), None
        )
        if program:
            lines.append(f"Canonical program: {program.name} ({program.id}).")
        elif program_name:
            missing.append(
                f"Program text '{program_name}' is not canonically resolved."
            )
        else:
            missing.append(
                "No canonical program association is present for this event."
            )
        facility_id = (
            event.get("facility_id")
            if isinstance(event.get("facility_id"), str)
            else None
        )
        facility = next(
            (item for item in environment.facilities if item.id == facility_id), None
        )
        if facility:
            lines.append(f"Canonical facility: {facility.name} ({facility.id}).")
        else:
            missing.append(
                "No canonical facility association is present for this event; account headquarters geography is not used as an event location."
            )
        if evidence_state != EvidenceState.CONFIRMED.value:
            missing.append(f"Event evidence is {evidence_state}, not confirmed.")
        action: str | None = None
        if account is not None and (
            "actionable" in question
            or "matter to btx" in question
            or "why does this matter" in question
            or "what does this mean" in question
        ):
            alerts = CommercialAlertEngine().evaluate(
                environment.commercial_contexts,
                environment.quotes,
                observed_at=observed_at,
                orders=environment.orders,
            )
            account_alerts = [
                alert for alert in alerts if alert.account_id == account.id
            ]
            account_work_items = [
                item
                for item in work_items
                if getattr(item, "account_id", None) == account.id
            ]
            if account_alerts:
                action = account_alerts[0].recommended_action
                lines.append(
                    f"In the current SAMPLE commercial dataset, a governed commercial alert recommends: {action}"
                )
            else:
                lines.append(
                    "No governed commercial alert currently connects this resolved account to a seller recommendation."
                )
            if account_work_items:
                lines.append(
                    f"Current governed work items for this account: {len(account_work_items)} (session-only SAMPLE workflow state)."
                )
            else:
                lines.append(
                    "No current governed work item was found for this account."
                )
        lines.append(
            "Public event facts remain source-backed. Any commercial, score, alert, or workflow context above is explicitly from the current SAMPLE commercial dataset. Omni is read-only and cannot create actions or CRM records."
        )
        provenance = [
            AssistantProvenance.STORED_INTELLIGENCE,
            AssistantProvenance.CANONICAL_FACT,
        ]
        if action or account is not None:
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines),
            account.id if account else "",
            tuple(dict.fromkeys(citations)),
            tuple(provenance),
            tuple(dict.fromkeys(missing)),
            action,
            tuple(dict.fromkeys(citation_links)),
            account.legal_name if account else None,
            context_used=context_used,
        )

    @staticmethod
    def _cross_account_market(
        context: Mapping[str, object], question: str
    ) -> tuple[str | None, dict[str, object], tuple[str, ...]]:
        """Use only exact canonical market values from the question or typed UI filter."""
        markets = (
            "Commercial Aerospace",
            "Defense",
            "Robotics",
            "Semiconductor",
            "Space",
            "Energy",
            "Medical",
        )
        explicit = next(
            (
                market
                for market in markets
                if re.search(rf"\b{re.escape(market.casefold())}\b", question)
            ),
            None,
        )
        if explicit:
            return explicit, {}, ()
        filters = context.get("active_filters")
        if not isinstance(filters, Mapping) or not filters:
            return None, {}, ()
        market = filters.get("market")
        if isinstance(market, str) and market in markets:
            return market, {"filters": {"market": market}}, ()
        if market is not None:
            return (
                None,
                {},
                (
                    "The supplied market filter is unsupported for this query and was not fuzzy-matched.",
                ),
            )
        return None, {}, ()

    @staticmethod
    def _canonical_scores(
        environment: SampleEnvironment, observed_at
    ) -> list[tuple[object, object]]:
        """Read existing deterministic scoring outputs; this does not add Omni scoring logic."""
        scores: list[tuple[object, object]] = []
        for account in environment.accounts:
            if account.id not in environment.scoring_inputs:
                continue
            scenario = environment.priority_scenarios.get(account.id) or environment.rich_scenarios.get(account.id)
            result = seller_attractiveness_projection(environment.attractiveness_inputs(account.id), calculated_at=observed_at, excluded=bool(scenario and scenario.exclusion_reason), exclusion_reason=scenario.exclusion_reason if scenario else None)
            if result.score is not None:
                scores.append((account, result))
        return scores

    @staticmethod
    def _open_work_items(work_items: Iterable[object]) -> tuple[object, ...]:
        return tuple(
            item
            for item in work_items
            if getattr(
                getattr(item, "status", None), "value", getattr(item, "status", "")
            )
            not in {"COMPLETED", "CANCELED"}
        )

    def _cross_account_answer(
        self,
        environment: SampleEnvironment,
        *,
        intent: str,
        question: str,
        observed_at,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
    ) -> OmniResponse:
        """Compose bounded canonical cross-account reads; no query DSL or independent decisioning."""
        if intent == "COMPARE":
            return self._compare_accounts_answer(environment, question, observed_at)
        market, context_used, filter_missing = self._cross_account_market(
            context, question
        )
        researched = [
            account
            for account in environment.accounts
            if account.public_identity
            and (market is None or market in account.industries)
        ]
        account_by_id = {account.id: account for account in researched}
        canonical_account_ids = {account.id for account in environment.accounts}
        missing = list(filter_missing)
        citations: list[str] = []
        links: list[OmniCitation] = []

        if intent == "SCORE_RANKING":
            scored = [
                (account, result)
                for account, result in self._canonical_scores(environment, observed_at)
                if account.id in account_by_id
            ]
            scored.sort(
                key=lambda item: (
                    -item[1].score,
                    item[0].legal_name.casefold(),
                    item[0].id,
                )
            )
            unavailable = [
                account
                for account in researched
                if account.id not in {candidate.id for candidate, _ in scored}
            ]
            if unavailable:
                missing.append(
                    f"{len(unavailable)} matching account(s) have no available canonical attractiveness score."
                )
            if not scored:
                return self._cross_empty_answer(
                    "No matching accounts have an available canonical attractiveness score.",
                    context_used,
                    missing,
                )
            selected = scored[:5]
            lines = [
                f"Ranked by the existing canonical Account Attractiveness score{f' for {market}' if market else ''}:"
            ]
            for account, score in selected:
                lines.append(
                    f"{account.legal_name}: {score.score} (coverage {score.coverage})."
                )
                if account.provenance:
                    citations.append(account.provenance.source_record_id)
            lines.append(
                "Scores use the established deterministic scoring service and current SAMPLE commercial inputs; Omni does not add a separate priority score."
            )
            return OmniResponse(
                " ".join(lines),
                "",
                tuple(dict.fromkeys(citations)),
                (
                    AssistantProvenance.CANONICAL_FACT,
                    AssistantProvenance.DETERMINISTIC_DERIVATION,
                )
                + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
                tuple(missing),
                "Review the listed Account 360 records before acting.",
                (),
                None,
                context_used=context_used,
            )

        open_items = self._open_work_items(work_items)
        actions_by_account: dict[str, list[object]] = {}
        for item in open_items:
            if getattr(item, "account_id", None) in account_by_id:
                actions_by_account.setdefault(item.account_id, []).append(item)
            elif getattr(item, "account_id", None) not in canonical_account_ids:
                missing.append(
                    f"Open work item {getattr(item, 'id', 'unknown')} has no canonical account in this query scope."
                )

        events_by_account: dict[str, list[Mapping[str, object]]] = {}
        for event in intelligence_events:
            account_id = event.get("account_id")
            if isinstance(account_id, str) and account_id in account_by_id:
                events_by_account.setdefault(account_id, []).append(event)
            elif event.get("account_id") is None:
                missing.append(
                    "A canonical Intelligence event is unresolved to an account and was not attached to a cross-account result."
                )

        if intent == "OPEN_ACTIONS":
            return self._open_actions_cross_answer(
                account_by_id, actions_by_account, context_used, missing
            )
        if intent == "INTELLIGENCE":
            return self._intelligence_cross_answer(
                account_by_id, events_by_account, context_used, missing
            )
        if intent == "INTELLIGENCE_OPEN_ACTIONS":
            matching = sorted(
                (
                    (
                        account_by_id[account_id],
                        events_by_account[account_id],
                        actions_by_account[account_id],
                    )
                    for account_id in events_by_account.keys()
                    & actions_by_account.keys()
                ),
                key=lambda item: (item[0].legal_name.casefold(), item[0].id),
            )
            if not matching:
                return self._cross_empty_answer(
                    "No canonical accounts appear in both the current Intelligence and open-work sets.",
                    context_used,
                    missing,
                )
            lines = [
                "Accounts appearing in both canonical Intelligence and open governed work sets:"
            ]
            citations = []
            links = []
            for account, events, actions in matching[:5]:
                event = max(events, key=self._event_sort_key)
                action = min(actions, key=self._work_sort_key)
                lines.append(
                    f"{account.legal_name}: Intelligence '{event.get('title') or event.get('id')}' and {len(actions)} open work item(s), including {getattr(action, 'summary', action.id)}."
                )
                citations.extend(str(value) for value in event.get("evidence_ids", ()))
                citations.extend(getattr(action, "evidence_ids", ()))
                if isinstance(event.get("source_url"), str):
                    links.append(
                        OmniCitation(
                            str(event.get("title") or "Intelligence event"),
                            str(event["source_url"]),
                        )
                    )
            lines.append(
                "This is a set intersection only; it does not establish that an Intelligence event caused a work item. Work items are session-only SAMPLE workflow state; public Intelligence remains source-backed."
            )
            return OmniResponse(
                " ".join(lines),
                "",
                tuple(dict.fromkeys(citations)),
                (
                    AssistantProvenance.STORED_INTELLIGENCE,
                    AssistantProvenance.DETERMINISTIC_DERIVATION,
                )
                + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
                tuple(dict.fromkeys(missing)),
                None,
                tuple(dict.fromkeys(links)),
                None,
                context_used=context_used,
            )

        assert intent == "QUOTES"
        return self._quotes_cross_answer(
            environment, researched, market, question, context_used, missing
        )

    @staticmethod
    def _event_sort_key(event: Mapping[str, object]) -> tuple[str, str]:
        observed = event.get("observed_at")
        value = (
            observed.isoformat()
            if hasattr(observed, "isoformat")
            else str(observed or "")
        )
        return value, str(event.get("id") or "")

    @staticmethod
    def _work_sort_key(item: object) -> tuple[int, str, str]:
        priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        created = getattr(item, "created_at", None)
        return (
            priority.get(getattr(item, "priority", ""), 9),
            str(created or ""),
            str(getattr(item, "id", "")),
        )

    def _open_actions_cross_answer(
        self,
        account_by_id: Mapping[str, object],
        actions_by_account: Mapping[str, list[object]],
        context_used: dict[str, object],
        missing: list[str],
    ) -> OmniResponse:
        selected = sorted(
            (
                (account_by_id[account_id], items)
                for account_id, items in actions_by_account.items()
            ),
            key=lambda item: (
                self._work_sort_key(min(item[1], key=self._work_sort_key)),
                item[0].legal_name.casefold(),
                item[0].id,
            ),
        )[:5]
        if not selected:
            return self._cross_empty_answer(
                "No matching accounts have open governed work items.",
                context_used,
                missing,
            )
        citations: list[str] = []
        lines = ["Accounts with current open governed work items:"]
        for account, items in selected:
            lead = min(items, key=self._work_sort_key)
            status = getattr(
                getattr(lead, "status", None),
                "value",
                getattr(lead, "status", "unavailable"),
            )
            lines.append(
                f"{account.legal_name}: {len(items)} open item(s); highest existing priority {getattr(lead, 'priority', 'unavailable')}, status {status}; {getattr(lead, 'summary', lead.id)}."
            )
            citations.extend(getattr(lead, "evidence_ids", ()))
        lines.append(
            "This reads current session-only SAMPLE workflow state. Omni does not reprioritize, transition, or create work items."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)),
            None,
            (),
            None,
            context_used=context_used,
        )

    def _intelligence_cross_answer(
        self,
        account_by_id: Mapping[str, object],
        events_by_account: Mapping[str, list[Mapping[str, object]]],
        context_used: dict[str, object],
        missing: list[str],
    ) -> OmniResponse:
        selected = sorted(
            (
                (account_by_id[account_id], events)
                for account_id, events in events_by_account.items()
            ),
            key=lambda item: (
                self._event_sort_key(max(item[1], key=self._event_sort_key)),
                item[0].legal_name.casefold(),
                item[0].id,
            ),
            reverse=True,
        )[:5]
        if not selected:
            return self._cross_empty_answer(
                "No matching accounts have canonical Intelligence records associated with them.",
                context_used,
                missing,
            )
        citations: list[str] = []
        links: list[OmniCitation] = []
        lines = [
            "Accounts with canonical source-backed Intelligence records, ordered by the available canonical event date:"
        ]
        for account, events in selected:
            latest = max(events, key=self._event_sort_key)
            state = latest.get("evidence_state") or "MISSING"
            lines.append(
                f"{account.legal_name}: {latest.get('title') or latest.get('id')} (evidence {state}; {len(events)} canonical event(s))."
            )
            citations.extend(str(value) for value in latest.get("evidence_ids", ()))
            if isinstance(latest.get("source_url"), str):
                links.append(
                    OmniCitation(
                        str(latest.get("title") or "Intelligence event"),
                        str(latest["source_url"]),
                    )
                )
            if str(state) != EvidenceState.CONFIRMED.value:
                missing.append(
                    f"{account.legal_name}'s listed Intelligence evidence is {state}, not confirmed."
                )
        lines.append(
            "Unresolved events are excluded rather than attached by similarity; no event geography or Monitor relevance is inferred or recomputed."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.STORED_INTELLIGENCE,
                AssistantProvenance.CANONICAL_FACT,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)),
            None,
            tuple(dict.fromkeys(links)),
            None,
            context_used=context_used,
        )

    def _quotes_cross_answer(
        self,
        environment: SampleEnvironment,
        researched: list[object],
        market: str | None,
        question: str,
        context_used: dict[str, object],
        missing: list[str],
    ) -> OmniResponse:
        account_by_id = {account.id: account for account in researched}
        open_only = "open quote" in question
        quote_ids = {
            quote.account_id
            for quote in environment.quotes
            if quote.account_id in account_by_id
            and (not open_only or quote.status.value == "OPEN")
        }
        matches = sorted(
            (account_by_id[account_id] for account_id in quote_ids),
            key=lambda account: (account.legal_name.casefold(), account.id),
        )[:5]
        label = "open quotes" if open_only else "quote/RFQ history"
        if not matches:
            return self._cross_empty_answer(
                f"No matching researched accounts have canonical {label} in the current SAMPLE dataset.",
                context_used,
                missing,
            )
        scope = f" {market}" if market else ""
        lines = [
            f"The current SAMPLE commercial dataset contains {len(matches)}{scope} researched account(s) with {label}: {', '.join(account.legal_name for account in matches)}."
        ]
        lines.append(
            "Quote status is simulated BTX commercial context; company identity and market classification are researched public data. No RFQ numbers or capability claims are inferred."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            (),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)),
            "Review the matching Account 360 record before acting.",
            (),
            None,
            context_used=context_used,
        )

    def _compare_accounts_answer(
        self, environment: SampleEnvironment, question: str, observed_at
    ) -> OmniResponse:
        accounts = self._comparison_accounts_named(question, environment)
        if len(accounts) != 2:
            return OmniResponse(
                "I need exactly two canonical researched account names or governed aliases for a comparison. Omni does not resolve partial or fuzzy company references.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                (
                    "Exactly two canonical account identities were not resolved for comparison.",
                ),
                None,
                (),
                None,
            )
        lines = [
            f"Canonical comparison: {accounts[0].legal_name} and {accounts[1].legal_name}."
        ]
        citations: list[str] = []
        for account in accounts:
            score_text = "unavailable"
            if account.id in environment.scoring_inputs:
                score = seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
                    calculated_at=observed_at,
                )
                score_text = (
                    str(score.score) if score.score is not None else "insufficient data"
                )
            quote_count = sum(
                1 for quote in environment.quotes if quote.account_id == account.id
            )
            lines.append(
                f"{account.legal_name}: existing attractiveness {score_text}; canonical quote-history records {quote_count}."
            )
            if account.provenance:
                citations.append(account.provenance.source_record_id)
        if "higher" in question and all(
            account.id in environment.scoring_inputs for account in accounts
        ):
            scores = {
                account.id: seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
                    calculated_at=observed_at,
                ).score
                for account in accounts
            }
            if scores[accounts[0].id] != scores[accounts[1].id]:
                winner = max(
                    accounts,
                    key=lambda account: (
                        scores[account.id],
                        account.legal_name.casefold(),
                    ),
                )
                lines.append(
                    f"For the requested attractiveness-score dimension only, {winner.legal_name} is higher."
                )
            else:
                lines.append(
                    "For the requested attractiveness-score dimension, the existing canonical scores are tied."
                )
        lines.append(
            "Attractiveness and quote history are current SAMPLE commercial context; this is factual comparison, not a combined score or independent priority recommendation."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            ),
            (),
            None,
            (),
            None,
            context_used={
                "account_id": accounts[0].id,
                "related_account_id": accounts[1].id,
            },
        )

    @staticmethod
    def _comparison_accounts_named(
        question: str, environment: SampleEnvironment
    ) -> tuple[object, ...]:
        """Resolve exact canonical names/aliases and preserve the explicit question order."""
        resolved: list[tuple[int, object]] = []
        for account in environment.accounts:
            names = [account.legal_name]
            if account.public_identity:
                names.extend(alias.value for alias in account.public_identity.aliases)
            positions = [match.start() for name in names
                         if (match := re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', question))]
            if positions:
                resolved.append((min(positions), account))
        return tuple(
            account
            for _, account in sorted(resolved, key=lambda item: (item[0], item[1].id))
        )

    @staticmethod
    def _cross_empty_answer(
        content: str, context_used: dict[str, object], missing: list[str]
    ) -> OmniResponse:
        return OmniResponse(
            content,
            "",
            (),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.MISSING_UNAVAILABLE,
            ),
            tuple(dict.fromkeys(missing or [content])),
            None,
            (),
            None,
            context_used=context_used,
        )

    @staticmethod
    def _summary_context(
        context: Mapping[str, object], *, selected_key: str | None = None
    ) -> dict[str, object]:
        """Return only current UI context that actually bounded a summary."""
        used: dict[str, object] = {}
        surface = context.get("surface")
        if isinstance(surface, str):
            used["surface"] = surface
        filters = context.get("active_filters")
        if isinstance(filters, Mapping) and filters:
            used["filters"] = dict(filters)
        if selected_key:
            selected = context.get(selected_key)
            if isinstance(selected, str):
                field = selected_key.removeprefix("selected_")
                used[field] = selected
        return used

    @staticmethod
    def _visible_ids(context: Mapping[str, object]) -> tuple[str, ...]:
        values = context.get("visible_record_ids")
        if not isinstance(values, (list, tuple)):
            return ()
        return tuple(value for value in values[:50] if isinstance(value, str))

    def _screen_summary_answer(
        self,
        environment: SampleEnvironment,
        *,
        question: str,
        observed_at,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
    ) -> OmniResponse:
        """Summarize a supplied, bounded product view without reading the rendered UI."""
        surface = context.get("surface")
        if not isinstance(surface, str):
            return self._empty_screen_summary(
                "the current view does not identify a canonical surface", context
            )
        visible_ids = self._visible_ids(context)
        if surface == "TODAY":
            return self._today_screen_summary(
                environment,
                observed_at,
                context,
                intelligence_events,
                work_items,
                visible_ids,
            )
        if surface == "ACCOUNTS":
            return self._accounts_screen_summary(
                environment, observed_at, context, visible_ids
            )
        if surface == "ACCOUNT_DETAIL":
            return self._account_detail_screen_summary(
                environment, observed_at, context, intelligence_events
            )
        if surface == "INTELLIGENCE":
            return self._intelligence_screen_summary(
                context, intelligence_events, visible_ids
            )
        if surface == "MAP":
            return self._map_screen_summary(environment, observed_at, context)
        if surface == "ACTIONS":
            return self._actions_screen_summary(
                environment, context, work_items, visible_ids
            )
        if surface == "MONITOR":
            return self._empty_screen_summary(
                "Monitor exposes status and provenance, but no bounded seller-visible records for a summary",
                context,
            )
        return self._empty_screen_summary(
            f"the current surface '{surface}' is not supported", context
        )

    def _empty_screen_summary(
        self, reason: str, context: Mapping[str, object]
    ) -> OmniResponse:
        return OmniResponse(
            f"I don't have any canonical records in the current view context to summarize because {reason}. Omni does not inspect the DOM, screenshots, or an unbounded backend universe.",
            "",
            (),
            (AssistantProvenance.MISSING_UNAVAILABLE,),
            (
                "No resolvable canonical records were supplied for the current screen summary.",
            ),
            None,
            (),
            None,
            context_used=self._summary_context(context),
        )

    def _today_screen_summary(
        self,
        environment: SampleEnvironment,
        observed_at,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        work_items: Iterable[object],
        visible_ids: tuple[str, ...],
    ) -> OmniResponse:
        if not visible_ids:
            return self._empty_screen_summary(
                "Today did not supply visible record IDs", context
            )
        alerts = {
            item.id: item
            for item in CommercialAlertEngine().evaluate(
                environment.commercial_contexts,
                environment.quotes,
                observed_at=observed_at,
                orders=environment.orders,
            )
        }
        events = {
            str(item.get("id")): item
            for item in intelligence_events
            if isinstance(item.get("id"), str)
        }
        actions = {getattr(item, "id", ""): item for item in work_items}
        accounts = {item.id: item for item in environment.accounts}
        lines = ["Current Today view, using only the supplied visible records:"]
        citations: list[str] = []
        links: list[OmniCitation] = []
        unresolved: list[str] = []
        count = 0
        for record_id in visible_ids:
            if count == 5:
                break
            if record_id in alerts:
                alert = alerts[record_id]
                account = accounts.get(alert.account_id)
                lines.append(
                    f"Commercial alert: {account.legal_name if account else alert.account_id} — {alert.type.value}: {alert.trigger_reason}. Recommended focus: {alert.recommended_action}"
                )
                citations.extend(alert.evidence_ids)
            elif record_id in events:
                event = events[record_id]
                lines.append(
                    f"Intelligence: {event.get('title') or record_id}; relevance: {event.get('relevance_explanation') or 'not stated'}."
                )
                citations.extend(str(value) for value in event.get("evidence_ids", ()))
                if isinstance(event.get("source_url"), str):
                    links.append(
                        OmniCitation(
                            str(event.get("title") or "Intelligence event"),
                            str(event["source_url"]),
                        )
                    )
            elif record_id in actions:
                action = actions[record_id]
                lines.append(
                    f"Governed action: {getattr(action, 'summary', record_id)}; priority {getattr(action, 'priority', 'unavailable')}; status {getattr(getattr(action, 'status', None), 'value', getattr(action, 'status', 'unavailable'))}."
                )
                citations.extend(getattr(action, "evidence_ids", ()))
            else:
                unresolved.append(record_id)
                continue
            count += 1
        if count == 0:
            return self._empty_screen_summary(
                "none of Today’s supplied visible IDs resolved to canonical records",
                context,
            )
        missing = (
            [f"{len(unresolved)} supplied Today record ID(s) could not be resolved."]
            if unresolved
            else []
        )
        lines.append(
            "Commercial alerts and governed actions are from the current SAMPLE commercial dataset; public Intelligence remains source-backed. Omni is read-only."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(missing),
            None,
            tuple(dict.fromkeys(links)),
            None,
            context_used=self._summary_context(context),
        )

    def _accounts_screen_summary(
        self,
        environment: SampleEnvironment,
        observed_at,
        context: Mapping[str, object],
        visible_ids: tuple[str, ...],
    ) -> OmniResponse:
        if not visible_ids:
            return self._empty_screen_summary(
                "Accounts did not supply visible account IDs", context
            )
        accounts = {item.id: item for item in environment.accounts}
        alerts = CommercialAlertEngine().evaluate(
            environment.commercial_contexts,
            environment.quotes,
            observed_at=observed_at,
            orders=environment.orders,
        )
        alerts_by_account: dict[str, list[object]] = {}
        for alert in alerts:
            alerts_by_account.setdefault(alert.account_id, []).append(alert)
        lines = ["Current Accounts view, using only the supplied visible accounts:"]
        citations: list[str] = []
        unresolved: list[str] = []
        count = 0
        for account_id in visible_ids:
            account = accounts.get(account_id)
            if account is None:
                unresolved.append(account_id)
                continue
            if count == 5:
                break
            score_text = "no canonical score input"
            if account.id in environment.scoring_inputs:
                score = seller_attractiveness_projection(
                    environment.attractiveness_inputs(account.id),
                    calculated_at=observed_at,
                )
                score_text = f"attractiveness {score.score if score.score is not None else 'insufficient data'} (coverage {score.coverage})"
            account_alerts = alerts_by_account.get(account.id, [])
            alert_text = (
                f"; alert {account_alerts[0].type.value}" if account_alerts else ""
            )
            lines.append(f"{account.legal_name}: {score_text}{alert_text}.")
            if account.provenance:
                citations.append(account.provenance.source_record_id)
            citations.extend(
                value for alert in account_alerts for value in alert.evidence_ids
            )
            count += 1
        if count == 0:
            return self._empty_screen_summary(
                "none of the supplied account IDs resolved", context
            )
        missing = (
            [f"{len(unresolved)} supplied account ID(s) could not be resolved."]
            if unresolved
            else []
        )
        lines.append(
            "Attractiveness and commercial alerts use existing deterministic services; commercial context is the current SAMPLE commercial dataset."
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(missing),
            "Review the visible Account 360 records before acting.",
            (),
            None,
            context_used=self._summary_context(context),
        )

    def _account_detail_screen_summary(
        self,
        environment: SampleEnvironment,
        observed_at,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
    ) -> OmniResponse:
        selected_id = context.get("selected_account_id")
        account = (
            next(
                (item for item in environment.accounts if item.id == selected_id), None
            )
            if isinstance(selected_id, str)
            else None
        )
        if account is None:
            return self._empty_screen_summary(
                "Account Detail has no selected canonical account", context
            )
        alerts = [
            item
            for item in CommercialAlertEngine().evaluate(
                environment.commercial_contexts,
                environment.quotes,
                observed_at=observed_at,
                orders=environment.orders,
            )
            if item.account_id == account.id
        ]
        events = [
            item for item in intelligence_events if item.get("account_id") == account.id
        ][:3]
        citations = [account.provenance.source_record_id] if account.provenance else []
        lines = [f"Account Detail summary for {account.legal_name}."]
        if account.id in environment.scoring_inputs:
            score = seller_attractiveness_projection(
                environment.attractiveness_inputs(account.id),
                calculated_at=observed_at,
            )
            lines.append(
                f"Existing deterministic attractiveness: {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}."
            )
        else:
            lines.append("No canonical attractiveness input is mapped to this account.")
        if alerts:
            lines.append(
                "Current governed commercial alerts: "
                + ", ".join(alert.type.value for alert in alerts[:3])
                + "."
            )
            citations.extend(value for alert in alerts for value in alert.evidence_ids)
        if events:
            lines.append(
                "Recent canonical Intelligence: "
                + "; ".join(
                    str(event.get("title") or event.get("id")) for event in events
                )
                + "."
            )
            citations.extend(
                str(value)
                for event in events
                for value in event.get("evidence_ids", ())
            )
        else:
            lines.append(
                "No canonical Intelligence records are represented for this account in the supplied Monitor read."
            )
        lines.append(
            "Public identity and Intelligence are source-backed; score, commercial alerts, and workflow context are from the current SAMPLE commercial dataset."
        )
        return OmniResponse(
            " ".join(lines),
            account.id,
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            ),
            (),
            alerts[0].recommended_action if alerts else None,
            (),
            account.legal_name,
            context_used=self._summary_context(
                context, selected_key="selected_account_id"
            ),
        )

    def _intelligence_screen_summary(
        self,
        context: Mapping[str, object],
        intelligence_events: Iterable[Mapping[str, object]],
        visible_ids: tuple[str, ...],
    ) -> OmniResponse:
        if not visible_ids:
            return self._empty_screen_summary(
                "Intelligence did not supply visible event IDs", context
            )
        events = {
            str(item.get("id")): item
            for item in intelligence_events
            if isinstance(item.get("id"), str)
        }
        selected = context.get("selected_event_id")
        lines = ["Current Intelligence view, using only the supplied visible events:"]
        citations: list[str] = []
        links: list[OmniCitation] = []
        unresolved: list[str] = []
        count = 0
        for event_id in visible_ids:
            event = events.get(event_id)
            if event is None:
                unresolved.append(event_id)
                continue
            if count == 5:
                break
            focused = "Selected event: " if event_id == selected else ""
            resolution = str(event.get("resolution_state") or "UNRESOLVED")
            lines.append(
                f"{focused}{event.get('title') or event_id} — {event.get('kind') or 'INTELLIGENCE_EVENT'}, {resolution}; relevance: {event.get('relevance_explanation') or 'not stated'}."
            )
            citations.extend(str(value) for value in event.get("evidence_ids", ()))
            if isinstance(event.get("source_url"), str):
                links.append(
                    OmniCitation(
                        str(event.get("title") or "Intelligence event"),
                        str(event["source_url"]),
                    )
                )
            count += 1
        if count == 0:
            return self._empty_screen_summary(
                "none of the supplied Intelligence event IDs resolved", context
            )
        missing = (
            [
                f"{len(unresolved)} supplied Intelligence event ID(s) could not be resolved."
            ]
            if unresolved
            else []
        )
        lines.append(
            "These are source-backed canonical Monitor records. Unresolved account, program, or facility links remain unresolved; Omni does not infer them."
        )
        selected_key = (
            "selected_event_id"
            if isinstance(selected, str)
            and selected in events
            and selected in visible_ids
            else None
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.STORED_INTELLIGENCE,
                AssistantProvenance.CANONICAL_FACT,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(missing),
            None,
            tuple(dict.fromkeys(links)),
            None,
            context_used=self._summary_context(context, selected_key=selected_key),
        )

    def _map_screen_summary(
        self, environment: SampleEnvironment, observed_at, context: Mapping[str, object]
    ) -> OmniResponse:
        facility_id = context.get("selected_facility_id")
        if isinstance(facility_id, str):
            return self._selected_facility_answer(
                environment,
                facility_id=facility_id,
                question="why does this facility matter",
                observed_at=observed_at,
                context=context,
            )
        account_id = context.get("selected_account_id")
        account = (
            next((item for item in environment.accounts if item.id == account_id), None)
            if isinstance(account_id, str)
            else None
        )
        if account is None:
            return self._empty_screen_summary(
                "Map has no selected canonical account or facility", context
            )
        return OmniResponse(
            f"Map focus: {account.legal_name} ({account.id}), a canonical researched account in {primary_market_label(account.industries)}. This summary describes only the selected map account; Omni does not infer map-wide priority, relationships, or event geography from proximity.",
            account.id,
            (account.provenance.source_record_id,) if account.provenance else (),
            (AssistantProvenance.CANONICAL_FACT,),
            (),
            None,
            (),
            account.legal_name,
            context_used=self._summary_context(
                context, selected_key="selected_account_id"
            ),
        )

    def _actions_screen_summary(
        self,
        environment: SampleEnvironment,
        context: Mapping[str, object],
        work_items: Iterable[object],
        visible_ids: tuple[str, ...],
    ) -> OmniResponse:
        if not visible_ids:
            return self._empty_screen_summary(
                "Actions did not supply visible work-item IDs", context
            )
        items = {getattr(item, "id", ""): item for item in work_items}
        accounts = {item.id: item for item in environment.accounts}
        selected = context.get("selected_action_id")
        lines = [
            "Current Actions view, using only the supplied visible governed work items:"
        ]
        citations: list[str] = []
        unresolved: list[str] = []
        count = 0
        for action_id in visible_ids:
            item = items.get(action_id)
            if item is None:
                unresolved.append(action_id)
                continue
            if count == 5:
                break
            account = accounts.get(getattr(item, "account_id", ""))
            focused = "Selected action: " if action_id == selected else ""
            status = getattr(
                getattr(item, "status", None),
                "value",
                getattr(item, "status", "unavailable"),
            )
            lines.append(
                f"{focused}{getattr(item, 'summary', action_id)} — priority {getattr(item, 'priority', 'unavailable')}, status {status}, account {account.legal_name if account else getattr(item, 'account_id', 'unresolved')}."
            )
            citations.extend(getattr(item, "evidence_ids", ()))
            count += 1
        if count == 0:
            return self._empty_screen_summary(
                "none of the supplied Action IDs resolved in the current authorized view",
                context,
            )
        missing = (
            [
                f"{len(unresolved)} supplied Action ID(s) could not be resolved in the current view."
            ]
            if unresolved
            else []
        )
        lines.append(
            "Actions are durable governed work. Omni reports them read-only and does not execute or reprioritize work."
        )
        selected_key = (
            "selected_action_id"
            if isinstance(selected, str)
            and selected in items
            and selected in visible_ids
            else None
        )
        return OmniResponse(
            " ".join(lines),
            "",
            tuple(dict.fromkeys(citations)),
            (
                AssistantProvenance.CANONICAL_FACT,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            )
            + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(missing),
            None,
            (),
            None,
            context_used=self._summary_context(context, selected_key=selected_key),
        )

    @staticmethod
    def _unscoped_answer(
        environment: SampleEnvironment, *, observed_at, question: str
    ) -> OmniResponse:
        """Ground a general seller question in the loaded curated universe, not a generic refusal."""
        if OmniOrchestrator._is_conversational_follow_up(question):
            return OmniResponse(
                "I need a specific Customer, event, facility, or Action to answer that follow-up. Select or name one; Omni will not reconstruct canonical context from prior assistant prose.",
                "",
                (),
                (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("No unambiguous canonical conversational referent is available.",),
                None,
                (),
                None,
            )
        researched = [item for item in environment.accounts if item.public_identity]
        if "open quote" in question:
            market = next(
                (
                    market
                    for market in (
                        "Commercial Aerospace",
                        "Defense",
                        "Robotics",
                        "Semiconductor",
                        "Space",
                        "Energy",
                        "Medical",
                    )
                    if market.casefold() in question
                ),
                None,
            )
            quoted_ids = {
                quote.account_id
                for quote in environment.quotes
                if quote.status.value == "OPEN"
            }
            matches = [
                account.legal_name
                for account in researched
                if account.id in quoted_ids
                and (market is None or market in account.industries)
            ]
            scope = f" {market}" if market else ""
            return OmniResponse(
                f"The current SAMPLE commercial dataset contains {len(matches)}{scope} researched account(s) with open quotes: {', '.join(matches) or 'none'}. Quote status is simulated BTX commercial context; company identity and market classification are researched public data.",
                "",
                (),
                (
                    AssistantProvenance.CANONICAL_FACT,
                    AssistantProvenance.DETERMINISTIC_DERIVATION,
                ),
                (),
                "Review the matching Account 360 record before acting.",
                (),
                None,
            )
        alerts = CommercialAlertEngine().evaluate(
            environment.commercial_contexts,
            environment.quotes,
            observed_at=observed_at,
            orders=environment.orders,
        )
        account_by_id = {item.id: item for item in researched}
        priority_items = [
            f"{account_by_id[alert.account_id].legal_name}: {alert.recommended_action}"
            for alert in alerts
            if alert.account_id in account_by_id
        ][:3]
        events = list(environment.intelligence_events)
        names = ", ".join(item.legal_name for item in researched[:6])
        event_links = tuple(
            OmniCitation(event.title, event.source_url) for event in events[:3]
        )
        event_ids = tuple(event.source_id for event in events[:3])
        comparison = (
            " Name the companies you want to compare, or select one from Account 360 for focused context."
            if "compare" in question
            else ""
        )
        action_summary = (
            "; ".join(priority_items)
            if priority_items
            else "No simulated workflow suggestions are loaded."
        )
        return OmniResponse(
            f"Deterministic POC guidance from the curated public-company universe: {len(researched)} researched companies and {len(events)} sourced public events are loaded. Available companies include {names}. Simulated BTX workflow suggestions to review: {action_summary}.{comparison} Public identity and event links are sourced; commercial, CRM, quote, scoring, and workflow context is simulated POC data. This is a deterministic fallback, not model-generated advice, and Omni cannot write to CRM.",
            "",
            event_ids,
            (
                AssistantProvenance.STORED_INTELLIGENCE,
                AssistantProvenance.DETERMINISTIC_DERIVATION,
            ),
            (
                "No account context was selected or resolved; this is a curated-universe overview.",
            ),
            "Select an Account 360 record or mention a company name to review its public evidence and simulated POC context.",
            event_links,
            None,
        )

    @staticmethod
    def reactive_public_research_contract(*, permitted: bool) -> str:
        return "PERMITTED_EPHEMERAL_PROVENANCED" if permitted else "UNAVAILABLE"
