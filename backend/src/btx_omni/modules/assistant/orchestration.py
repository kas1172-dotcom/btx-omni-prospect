"""Bounded Omni POC orchestration over supplied governed read models only."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
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

    def answer(self, environment: SampleEnvironment, *, account_id: str | None, question: str, observed_at, context: dict[str, object] | None = None, intelligence_events: Iterable[Mapping[str, object]] | None = None, work_items: Iterable[object] = ()) -> OmniResponse:
        """Bounded deterministic retrieval fallback; it never presents itself as model output."""
        query = question.casefold().strip()
        accounts = list(environment.accounts)
        product_context = context or {}
        if "open quote" in query:
            return self._unscoped_answer(environment, observed_at=observed_at, question=query)
        selected_event_id = product_context.get("selected_event_id")
        if isinstance(selected_event_id, str) and self._is_event_question(query):
            event_records = tuple(intelligence_events) if intelligence_events is not None else self._sample_event_records(environment)
            return self._selected_event_answer(environment, event_records=event_records, work_items=work_items, event_id=selected_event_id, question=query, observed_at=observed_at, context=product_context)
        selected_facility_id = product_context.get("selected_facility_id")
        if isinstance(selected_facility_id, str) and self._is_facility_question(query):
            return self._selected_facility_answer(
                environment,
                facility_id=selected_facility_id,
                question=query,
                observed_at=observed_at,
                context=product_context,
            )
        session_account_id = product_context.get("session_account_id")
        session_id = session_account_id if isinstance(session_account_id, str) else None
        account = next((item for item in accounts if item.id == (account_id or session_id)), None)
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
    def _is_event_question(question: str) -> bool:
        return any(phrase in question for phrase in (
            "what happened", "why does this matter", "what does this mean", "who is this about",
            "what evidence", "evidence supports", "is this actionable", "this award", "this event",
        ))

    @staticmethod
    def _is_facility_question(question: str) -> bool:
        return any(phrase in question for phrase in (
            "this facility", "what is this facility", "who owns this facility",
            "which account is this facility", "what do we know about this location",
            "evidence supports this facility", "facility record", "btx context for this facility",
        ))

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
        researched = next((item for item in environment.public_facilities if item.id == facility_id), None)
        btx = next((item for item in environment.btx_facilities if item.id == facility_id), None)
        context_used: dict[str, object] = {"facility_id": facility_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if researched is None and btx is None:
            return OmniResponse(
                "I can't resolve the selected facility to a canonical facility record in the current dataset. I will not match it by name, coordinates, or proximity.",
                "", (), (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Selected facility is unavailable or stale.",), None, (), None,
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
        account = next((item for item in environment.accounts if item.id == facility.account_id), None)
        citations = list(facility.provenance.source_ids if facility.provenance else ())
        citation_links = [OmniCitation(facility.name, facility.source_url)] if facility.source_url else []
        missing: list[str] = []
        lines = [
            f"Canonical researched facility: {facility.name} ({facility.id}). ",
            f"Facility type: {facility.facility_type}. Location: {self._location_text(facility)}.",
            f"Verification state: {facility.verification_state}; source type: {facility.source_type or 'unavailable'}.",
        ]
        if facility.source_url:
            lines.append("The facility's researched public source is cited with this response.")
        else:
            missing.append("No source URL is present for this canonical facility record.")
        if account is None:
            lines.append("This facility is present in the canonical researched-facility dataset, but no canonical researched account association is established for it here.")
            missing.append("No canonical parent account is associated with this facility.")
        else:
            lines.append(f"Canonical parent account: {account.legal_name} ({account.id}).")
            selected_account_id = context.get("selected_account_id")
            if isinstance(selected_account_id, str) and selected_account_id != account.id:
                lines.append("The UI-selected account does not match this facility's canonical parent account; facility facts use the canonical facility association.")
                missing.append("Selected account context conflicts with the facility's canonical parent account.")

        action: str | None = None
        if account is not None and "matter" in question:
            context_used["account_id"] = account.id
            score = None
            if account.id in environment.scoring_inputs:
                score = calculate_account_attractiveness(
                    AccountAttractivenessInputs(environment.scoring_inputs[account.id]),
                    evidence_ids=tuple(citations),
                    calculated_at=observed_at,
                )
                lines.append(f"This facility has no separate facility score. Its parent account's deterministic attractiveness is {score.score if score.score is not None else 'insufficient data'} with coverage {score.coverage}.")
                missing.extend(score.missingness)
            else:
                missing.append("No canonical account-attractiveness input is mapped to this facility's parent account.")
            alerts = CommercialAlertEngine().evaluate(environment.commercial_contexts, environment.quotes, observed_at=observed_at, orders=environment.orders)
            account_alerts = [item for item in alerts if item.account_id == account.id]
            if account_alerts:
                action = account_alerts[0].recommended_action
                lines.append(f"In the current SAMPLE commercial dataset, the parent account has a governed alert recommending: {action}")
            else:
                lines.append("No governed commercial alert currently connects this parent account to a seller recommendation.")
        lines.append("This describes the canonical facility record only. Geographic proximity is not used to infer ownership, relationships, or commercial importance. Any commercial context above is from the current SAMPLE commercial dataset; Omni is read-only.")
        provenance = [AssistantProvenance.CANONICAL_FACT]
        if action or "account_id" in context_used:
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines), account.id if account else "", tuple(dict.fromkeys(citations)), tuple(provenance),
            tuple(dict.fromkeys(missing)), action, tuple(dict.fromkeys(citation_links)), account.legal_name if account else None,
            context_used=context_used,
        )

    def _selected_btx_facility_answer(self, environment: SampleEnvironment, *, facility, context_used: dict[str, object]) -> OmniResponse:
        business_unit = next((item for item in environment.business_units if item.id == facility.business_unit_id), None)
        citations = [facility.provenance.source_record_id]
        citation_links = [OmniCitation(facility.name, facility.source_url)] if facility.source_url else []
        missing: list[str] = []
        lines = [
            f"Canonical BTX facility: {facility.name} ({facility.id}). Location: {self._location_text(facility)}.",
            f"Verification state: {facility.verification_state}; source type: {facility.source_type or 'unavailable'}.",
        ]
        if facility.source_url:
            lines.append("The facility's public BTX business-unit source is cited with this response.")
        else:
            missing.append("No source URL is present for this canonical BTX facility record.")
        if business_unit is None:
            lines.append("No canonical BTX business-unit association is present for this facility.")
            missing.append("No canonical BTX business-unit association is present for this facility.")
        else:
            lines.append(f"Canonical BTX business unit: {business_unit.name} ({business_unit.id}).")
            if business_unit.processes:
                lines.append(f"Publicly documented processes: {', '.join(business_unit.processes)}.")
        lines.append("This is a public BTX business-unit facility profile, not a production-capacity or prospect/customer record. No customer or prospect account association is inferred. Geographic proximity is not used to infer relationships or commercial importance.")
        return OmniResponse(
            " ".join(lines), "", tuple(dict.fromkeys(citations)), (AssistantProvenance.CANONICAL_FACT,) + ((AssistantProvenance.MISSING_UNAVAILABLE,) if missing else ()),
            tuple(dict.fromkeys(missing)), None, tuple(dict.fromkeys(citation_links)), None,
            context_used=context_used,
        )

    @staticmethod
    def _sample_event_records(environment: SampleEnvironment) -> tuple[dict[str, object], ...]:
        accounts = {item.id: item for item in environment.accounts}
        names = {item.legal_name: item.id for item in environment.accounts}
        records: list[dict[str, object]] = []
        for raw in environment.intelligence_events:
            provenance = accounts[names[raw.account_name]].provenance if raw.account_name in names else next(iter(accounts.values())).provenance
            signal = normalize_signal(raw, account_name_to_id=names, provenance=provenance)
            records.append({
                "id": signal.id, "kind": signal.kind.value, "title": signal.title,
                "source_url": signal.source_url, "account_id": signal.account_id,
                "program_name": signal.program_name, "program_id": None, "facility_id": None,
                "evidence_state": signal.evidence_state.value, "resolution_state": "RESOLVED" if signal.account_id else "UNRESOLVED",
                "data_mode": "CURATED_PUBLIC", "observed_at": signal.occurred_at,
                "relevance_explanation": signal.relevance_explanation, "evidence_ids": signal.evidence_ids,
                "source_tier": "CURATED_POC_PUBLIC", "provenance": signal.provenance,
            })
        return tuple(records)

    def _selected_event_answer(self, environment: SampleEnvironment, *, event_records: Iterable[Mapping[str, object]], work_items: Iterable[object], event_id: str, question: str, observed_at, context: Mapping[str, object]) -> OmniResponse:
        event = next((record for record in event_records if record.get("id") == event_id), None)
        context_used: dict[str, object] = {"event_id": event_id}
        if context.get("surface"):
            context_used["surface"] = str(context["surface"])
        if event is None:
            return OmniResponse(
                "The selected Intelligence event is not available in the current canonical Monitor read model. I cannot explain it or connect it to account history without a canonical event record.",
                "", (), (AssistantProvenance.MISSING_UNAVAILABLE,),
                ("Selected Intelligence event is unavailable or stale.",), None, (), None,
                context_used=context_used,
            )

        account_id = event.get("account_id") if isinstance(event.get("account_id"), str) else None
        account = next((item for item in environment.accounts if item.id == account_id), None)
        title = str(event.get("title") or "Untitled intelligence event")
        kind = str(event.get("kind") or "INTELLIGENCE_EVENT")
        source_url = event.get("source_url") if isinstance(event.get("source_url"), str) else None
        observed_at_value = event.get("observed_at")
        observed_text = observed_at_value.isoformat() if hasattr(observed_at_value, "isoformat") else str(observed_at_value or "unavailable")
        evidence_state = str(event.get("evidence_state") or "MISSING")
        resolution_state = str(event.get("resolution_state") or ("RESOLVED" if account else "UNRESOLVED"))
        citations = [str(value) for value in event.get("evidence_ids", ())]
        citation_links = [OmniCitation(title, source_url)] if source_url else []
        missing: list[str] = []
        lines = [f"Source-backed Intelligence event: {title}. Type: {kind}. Observed/source date: {observed_text}."]
        if source_url:
            lines.append("The supplied public source is cited with this response.")
        lines.append(f"Evidence state: {evidence_state}; canonical resolution state: {resolution_state}.")
        relevance = event.get("relevance_explanation")
        if relevance:
            lines.append(f"Seller relevance from the canonical Monitor projection: {relevance}")
        if account is None:
            lines.append("This event is currently unresolved to a canonical researched account, so it cannot be reliably connected to BTX account history, scoring, or workflow context.")
            missing.append("No canonical account resolution is present for this event.")
        else:
            context_used["account_id"] = account.id
            lines.append(f"Resolved organization: {account.legal_name} ({primary_market_label(account.industries)}).")
        program_id = event.get("program_id") if isinstance(event.get("program_id"), str) else None
        program_name = event.get("program_name") if isinstance(event.get("program_name"), str) else None
        program = next((item for item in environment.programs if item.id == program_id), None)
        if program:
            lines.append(f"Canonical program: {program.name} ({program.id}).")
        elif program_name:
            missing.append(f"Program text '{program_name}' is not canonically resolved.")
        else:
            missing.append("No canonical program association is present for this event.")
        facility_id = event.get("facility_id") if isinstance(event.get("facility_id"), str) else None
        facility = next((item for item in environment.facilities if item.id == facility_id), None)
        if facility:
            lines.append(f"Canonical facility: {facility.name} ({facility.id}).")
        else:
            missing.append("No canonical facility association is present for this event; account headquarters geography is not used as an event location.")
        if evidence_state != EvidenceState.CONFIRMED.value:
            missing.append(f"Event evidence is {evidence_state}, not confirmed.")
        action: str | None = None
        if account is not None and ("actionable" in question or "matter to btx" in question or "why does this matter" in question or "what does this mean" in question):
            alerts = CommercialAlertEngine().evaluate(environment.commercial_contexts, environment.quotes, observed_at=observed_at, orders=environment.orders)
            account_alerts = [alert for alert in alerts if alert.account_id == account.id]
            account_work_items = [item for item in work_items if getattr(item, "account_id", None) == account.id]
            if account_alerts:
                action = account_alerts[0].recommended_action
                lines.append(f"In the current SAMPLE commercial dataset, a governed commercial alert recommends: {action}")
            else:
                lines.append("No governed commercial alert currently connects this resolved account to a seller recommendation.")
            if account_work_items:
                lines.append(f"Current governed work items for this account: {len(account_work_items)} (session-only SAMPLE workflow state).")
            else:
                lines.append("No current governed work item was found for this account.")
        lines.append("Public event facts remain source-backed. Any commercial, score, alert, or workflow context above is explicitly from the current SAMPLE commercial dataset. Omni is read-only and cannot create actions or CRM records.")
        provenance = [AssistantProvenance.STORED_INTELLIGENCE, AssistantProvenance.CANONICAL_FACT]
        if action or account is not None:
            provenance.append(AssistantProvenance.DETERMINISTIC_DERIVATION)
        if missing:
            provenance.append(AssistantProvenance.MISSING_UNAVAILABLE)
        return OmniResponse(
            " ".join(lines), account.id if account else "", tuple(dict.fromkeys(citations)), tuple(provenance),
            tuple(dict.fromkeys(missing)), action, tuple(dict.fromkeys(citation_links)), account.legal_name if account else None,
            context_used=context_used,
        )

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
