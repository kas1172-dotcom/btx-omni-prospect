"""Bounded Omni POC orchestration over supplied governed read models only."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from btx_omni.domain.common import EvidenceState
from btx_omni.domain.markets import primary_market_label
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
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


class OmniOrchestrator:
    """No SQL, tools, writes, or source authority: only supplied POC facts."""

    def answer(self, environment: SampleEnvironment, *, account_id: str | None, question: str, observed_at, context: dict[str, str] | None = None) -> OmniResponse:
        """Bounded deterministic retrieval fallback; it never presents itself as model output."""
        query = question.casefold().strip()
        accounts = list(environment.accounts)
        product_context = context or {}
        session_account_id = product_context.get("session_account_id")
        account = next((item for item in accounts if item.id == (account_id or session_account_id)), None)
        if account is None:
            account = next((item for item in accounts if item.research_account_id and item.legal_name.casefold() in query), None)
        if account is None:
            return self._unscoped_answer(environment, observed_at=observed_at, question=query)
        alerts = CommercialAlertEngine().evaluate(environment.commercial_contexts, environment.quotes, observed_at=observed_at, orders=environment.orders)
        account_alerts = tuple(item for item in alerts if item.account_id == account.id)
        citations: list[str] = [account.provenance.source_record_id] if account.provenance else []
        citation_links: list[OmniCitation] = []
        if account.provenance and account.provenance.source_url:
            citation_links.append(OmniCitation("Public company identity", account.provenance.source_url))
        missing: list[str] = []
        lines = [f"Deterministic governed answer for {account.legal_name}. Public identity, location, and cited events are publicly verified; BTX commercial, CRM, ownership, deal, quote, scoring, and workflow context is simulated POC data."]
        public_identity_state = account.public_identity.verification_state.value if account.public_identity else "UNVERIFIED"
        lines.append(f"Public identity: {public_identity_state}; BTX commercial context is simulated and not a connected source record.")
        if account.public_relationship:
            lines.append(f"Public relationship evidence: {account.public_relationship.state.value} ({account.public_relationship.confidence}); it is not BTX internal confirmation.")
            citations.extend(account.public_relationship.provenance.source_ids)
        if account.public_contacts:
            lines.append(f"Contact Research: {len(account.public_contacts)} public research record(s), not CRM contacts.")
        if account_alerts:
            lines.append("Alerts: " + ", ".join(item.type.value for item in account_alerts) + ".")
            citations.extend(value for alert in account_alerts for value in alert.evidence_ids)
        commercial_contexts = [item for item in environment.commercial_contexts if item.account_id == account_id]
        if not commercial_contexts:
            missing.append("PRISM commercial context unavailable.")
        if ("score" in question.casefold() or "attractive" in question.casefold()) and account.id in environment.scoring_inputs:
            score = calculate_account_attractiveness(AccountAttractivenessInputs(environment.scoring_inputs[account.id]), evidence_ids=tuple(citations), calculated_at=observed_at)
            lines.append(f"Account Attractiveness: {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}.")
            missing.extend(score.missingness)
        elif "score" in question.casefold() or "attractive" in question.casefold():
            missing.append("Account Attractiveness is unavailable: no simulated BTX scoring input is mapped to this public identity.")
        events = [item for item in environment.intelligence_events if item.account_name == account.legal_name]
        if events:
            normalized = normalize_signal(events[0], account_name_to_id={item.legal_name: item.id for item in environment.accounts}, provenance=account.provenance)
            lines.append(f"Intelligence: {normalized.kind.value}; {normalized.relevance_explanation}")
            citations.extend(normalized.evidence_ids)
            citation_links.append(OmniCitation(normalized.title, normalized.source_url))
            if normalized.evidence_state is not EvidenceState.CONFIRMED:
                missing.append(f"Intelligence evidence is {normalized.evidence_state.value}, not confirmed.")
        pairs = [(component, quote) for component in environment.matching_components for quote in environment.matching_quotes if component.account_id == account_id and quote.account_id == account_id]
        if pairs:
            match = match_component_to_quote(*pairs[0])
            lines.append(f"Commercial matching: {match.method.value} ({match.review_state.value}).")
            citations.extend(match.evidence_ids)
        companies = [item for item in environment.crm_companies if item.account_id == account.id]
        if not companies:
            missing.append("CRM provider/account context unavailable.")
        else:
            company_ids = {item.id for item in companies}
            contacts = [item for item in environment.crm_contacts if item.company_id in company_ids]
            lines.append(f"CRM owner: {companies[0].owner_id}; shared role families: {', '.join(sorted({item.role_family for item in contacts}))}.")
            citations.extend(item.provenance.source_record_id for item in companies)
        action = account_alerts[0].recommended_action if account_alerts else "Review governed commercial context before taking action."
        if "compare" in query:
            peers = [item.legal_name for item in accounts if item.research_account_id and item.id != account.id and item.industries == account.industries][:3]
            lines.append(f"Comparable researched {primary_market_label(account.industries)} targets: {', '.join(peers) or 'none loaded'}.")
        lines.append("This is a deterministic fallback, not model-generated advice. Omni is read-only and cannot perform CRM writes.")
        context_used = {"account_id": account.id}
        if product_context.get("surface"):
            context_used["surface"] = str(product_context["surface"])
        return OmniResponse(" ".join(lines), account.id, tuple(dict.fromkeys(citations)), (AssistantProvenance.CANONICAL_FACT, AssistantProvenance.DETERMINISTIC_DERIVATION) + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()), tuple(dict.fromkeys(missing)), action, tuple(dict.fromkeys(citation_links)), account.legal_name, context_used=context_used)

    @staticmethod
    def _unscoped_answer(environment: SampleEnvironment, *, observed_at, question: str) -> OmniResponse:
        """Ground a general seller question in the loaded curated universe, not a generic refusal."""
        researched = [item for item in environment.accounts if item.research_account_id]
        if "open quote" in question:
            market = next((market for market in ("Aerospace", "Defense", "Semiconductor", "Space Exploration", "Energy", "Medical") if market.casefold() in question), None)
            quoted_ids = {quote.account_id for quote in environment.quotes if quote.status.value == "OPEN"}
            matches = [account.legal_name for account in researched if account.id in quoted_ids and (market is None or market in account.industries)]
            scope = f" {market}" if market else ""
            return OmniResponse(
                f"The current SAMPLE commercial dataset contains {len(matches)}{scope} researched account(s) with open quotes: {', '.join(matches) or 'none'}. Quote status is simulated BTX commercial context; company identity and market classification are researched public data.",
                "", (), (AssistantProvenance.CANONICAL_FACT, AssistantProvenance.DETERMINISTIC_DERIVATION), (),
                "Review the matching Account 360 record before acting.", (), None,
            )
        alerts = CommercialAlertEngine().evaluate(environment.commercial_contexts, environment.quotes, observed_at=observed_at, orders=environment.orders)
        account_by_id = {item.id: item for item in researched}
        priority_items = [
            f"{account_by_id[alert.account_id].legal_name}: {alert.recommended_action}"
            for alert in alerts
            if alert.account_id in account_by_id
        ][:3]
        events = list(environment.intelligence_events)
        names = ", ".join(item.legal_name for item in researched[:6])
        event_links = tuple(OmniCitation(event.title, event.source_url) for event in events[:3])
        event_ids = tuple(event.source_id for event in events[:3])
        comparison = " Name the companies you want to compare, or select one from Account 360 for focused context." if "compare" in question else ""
        action_summary = "; ".join(priority_items) if priority_items else "No simulated workflow suggestions are loaded."
        return OmniResponse(
            f"Deterministic POC guidance from the curated public-company universe: {len(researched)} researched companies and {len(events)} sourced public events are loaded. Available companies include {names}. Simulated BTX workflow suggestions to review: {action_summary}.{comparison} Public identity and event links are sourced; commercial, CRM, quote, scoring, and workflow context is simulated POC data. This is a deterministic fallback, not model-generated advice, and Omni cannot write to CRM.",
            "",
            event_ids,
            (AssistantProvenance.STORED_INTELLIGENCE, AssistantProvenance.DETERMINISTIC_DERIVATION),
            ("No account context was selected or resolved; this is a curated-universe overview.",),
            "Select an Account 360 record or mention a company name to review its public evidence and simulated POC context.",
            event_links,
            None,
        )

    @staticmethod
    def reactive_public_research_contract(*, permitted: bool) -> str:
        return "PERMITTED_EPHEMERAL_PROVENANCED" if permitted else "UNAVAILABLE"
