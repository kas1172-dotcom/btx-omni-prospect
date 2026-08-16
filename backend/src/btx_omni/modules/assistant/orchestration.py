"""Bounded Omni POC orchestration over supplied governed read models only."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from btx_omni.domain.common import EvidenceState
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
class OmniResponse:
    content: str
    account_id: str
    citations: tuple[str, ...]
    provenance: tuple[AssistantProvenance, ...]
    missingness: tuple[str, ...]
    recommended_action: str | None
    source_of_record: bool = False
    public_research_permitted: bool = False


class OmniOrchestrator:
    """No SQL, tools, writes, or source authority: only supplied POC facts."""

    def answer(self, environment: SampleEnvironment, *, account_id: str, question: str, observed_at) -> OmniResponse:
        account = next(item for item in environment.accounts if item.id == account_id)
        alerts = CommercialAlertEngine().evaluate(environment.commercial_contexts, environment.quotes, observed_at=observed_at)
        account_alerts = tuple(item for item in alerts if item.account_id == account_id)
        citations: list[str] = [account.provenance.source_record_id] if account.provenance else []
        missing: list[str] = []
        lines = [f"Canonical account: {account.legal_name} ({account.relationship.value})."]
        public_identity_state = account.public_identity.verification_state.value if account.public_identity else "UNVERIFIED"
        lines.append(f"Public identity: {public_identity_state}; BTX commercial context remains SAMPLE synthetic data.")
        if account_alerts:
            lines.append("Alerts: " + ", ".join(item.type.value for item in account_alerts) + ".")
            citations.extend(value for alert in account_alerts for value in alert.evidence_ids)
        context = [item for item in environment.commercial_contexts if item.account_id == account_id]
        if not context:
            missing.append("PRISM commercial context unavailable.")
        if "score" in question.casefold() or "attractive" in question.casefold():
            score = calculate_account_attractiveness(AccountAttractivenessInputs(environment.scoring_inputs[account_id]), evidence_ids=tuple(citations), calculated_at=observed_at)
            lines.append(f"Account Attractiveness: {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}.")
            missing.extend(score.missingness)
        events = [item for item in environment.intelligence_events if item.account_name == account.legal_name]
        if events:
            normalized = normalize_signal(events[0], account_name_to_id={item.legal_name: item.id for item in environment.accounts}, provenance=account.provenance)
            lines.append(f"Intelligence: {normalized.kind.value}; {normalized.relevance_explanation}")
            citations.extend(normalized.evidence_ids)
            if normalized.evidence_state is not EvidenceState.CONFIRMED:
                missing.append(f"Intelligence evidence is {normalized.evidence_state.value}, not confirmed.")
        pairs = [(component, quote) for component in environment.matching_components for quote in environment.matching_quotes if component.account_id == account_id and quote.account_id == account_id]
        if pairs:
            match = match_component_to_quote(*pairs[0])
            lines.append(f"Commercial matching: {match.method.value} ({match.review_state.value}).")
            citations.extend(match.evidence_ids)
        crm = next((item for item in environment.crm_contexts if item.account_id == account_id), None)
        if crm is None:
            missing.append("CRM provider/account context unavailable.")
        else:
            lines.append(f"CRM owner: {crm.owner_id}; shared role families: {', '.join(crm.contact_role_families)}.")
            citations.append(crm.provenance.source_record_id)
        action = account_alerts[0].recommended_action if account_alerts else "Review governed commercial context before taking action."
        lines.append("Omni is not a source of record and cannot perform CRM writes.")
        return OmniResponse(" ".join(lines), account_id, tuple(dict.fromkeys(citations)), (AssistantProvenance.CANONICAL_FACT, AssistantProvenance.DETERMINISTIC_DERIVATION) + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()), tuple(dict.fromkeys(missing)), action)

    @staticmethod
    def reactive_public_research_contract(*, permitted: bool) -> str:
        return "PERMITTED_EPHEMERAL_PROVENANCED" if permitted else "UNAVAILABLE"
