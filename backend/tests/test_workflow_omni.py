from dataclasses import replace
from datetime import UTC, datetime

import pytest

from btx_omni.domain.common import EvidenceState
from btx_omni.integrations.hubspot.contracts import (
    CrmProviderState,
    SampleHubSpotAdapter,
)
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.modules.intelligence.signals import (
    RawSignal,
    SignalKind,
    normalize_signal,
)
from btx_omni.modules.work.service import WorkService, WorkStatus
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def event_id_for(sample, account_id: str) -> str:
    raw = next(item for item in sample.intelligence_events if item.account_name and next(account.id for account in sample.accounts if account.legal_name == item.account_name) == account_id)
    names = {account.legal_name: account.id for account in sample.accounts}
    account = next(item for item in sample.accounts if item.id == account_id)
    return normalize_signal(raw, account_name_to_id=names, provenance=account.provenance).id


def test_governed_action_lifecycle_audit_and_idempotency() -> None:
    service = WorkService()
    first = service.create(account_id="acct-01-003", summary="Review dormant customer", evidence_ids=("ev-dormant",), idempotency_key="dormant-1", actor_id="seller", occurred_at=NOW, priority="HIGH")
    replay = service.create(account_id="acct-01-003", summary="ignored", evidence_ids=("ev-dormant",), idempotency_key="dormant-1", actor_id="seller", occurred_at=NOW)
    assert replay == first
    item = service.transition(first.id, WorkStatus.IN_REVIEW, actor_id="seller", occurred_at=NOW)
    item = service.transition(item.id, WorkStatus.ASSIGNED, actor_id="manager", owner_id="owner-1", occurred_at=NOW)
    item = service.transition(item.id, WorkStatus.APPROVED, actor_id="manager", occurred_at=NOW)
    item = service.transition(item.id, WorkStatus.FOLLOW_UP, actor_id="owner-1", occurred_at=NOW)
    item = service.transition(item.id, WorkStatus.COMPLETED, actor_id="owner-1", occurred_at=NOW)
    assert item.status is WorkStatus.COMPLETED and len(service.audit(item.id)) == 6
    dismissed = service.create(account_id="acct-01-004", summary="Dismiss", evidence_ids=("ev-quote",), idempotency_key="dismiss-1", actor_id="seller", occurred_at=NOW)
    assert service.transition(dismissed.id, WorkStatus.DISMISSED, actor_id="seller", occurred_at=NOW).status is WorkStatus.DISMISSED


def test_crm_preview_requires_explicit_confirmation_and_unavailability_is_truthful() -> None:
    service = WorkService()
    item = service.create(account_id="acct-01-004", summary="Follow up stale quote", evidence_ids=("ev-quote",), idempotency_key="quote-1", actor_id="seller", occurred_at=NOW)
    available = SampleHubSpotAdapter({})
    preview = service.preview_crm_action(item.id, available)
    with pytest.raises(PermissionError):
        available.execute_action(preview)
    assert service.confirm_and_execute_crm_action(preview, available).executed
    unavailable = SampleHubSpotAdapter({}, CrmProviderState.UNAVAILABLE)
    assert unavailable.account_context(item.account_id).detail == "HubSpot provider is unavailable."
    assert service.confirm_and_execute_crm_action(service.preview_crm_action(item.id, unavailable), unavailable).unavailable_reason


def test_omni_explains_alerts_coordination_matching_and_truthful_missingness() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    dormant = omni.answer(sample, account_id="applied-materials", question="Why is this dormant account at risk?", observed_at=NOW)
    stale = omni.answer(sample, account_id="lockheed-martin", question="What should we do about the quote?", observed_at=NOW)
    cross_bu = omni.answer(sample, account_id="boeing", question="Who needs coordination?", observed_at=NOW)
    defense = omni.answer(sample, account_id="lockheed-martin", question="Explain the award match and score", observed_at=NOW)
    external = omni.answer(sample, account_id="rocket-lab-usa", question="What do we know?", observed_at=NOW)
    assert dormant.recommended_action
    assert stale.citations and stale.recommended_action
    assert "CROSS_BU_COORDINATION" in cross_bu.content
    assert "AWARD_CONTRACT" in defense.content and "EXACT_PART" in defense.content
    assert external.citations
    assert not defense.source_of_record and "cannot perform CRM writes" in defense.content
    assert omni.reactive_public_research_contract(permitted=False) == "UNAVAILABLE"


def test_omni_supports_grounded_unscoped_and_session_follow_up_context() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    overview = omni.answer(sample, account_id=None, question="What should I review today?", observed_at=NOW)
    follow_up = omni.answer(sample, account_id=None, question="Explain this score and its gaps", observed_at=NOW, context={"session_account_id": "boeing"})
    assert "curated public-company universe" in overview.content
    assert overview.citation_links and overview.recommended_action
    assert follow_up.account_id == "boeing" and follow_up.account_name == "Boeing"
    assert "Account Attractiveness" in follow_up.content and "CROSS_BU_COORDINATION" in follow_up.content
    assert "cannot perform CRM writes" in follow_up.content


def test_omni_routes_a_selected_resolved_event_with_evidence_and_sample_boundary() -> None:
    sample = build_sample_environment()
    event_id = event_id_for(sample, "boeing")
    response = OmniOrchestrator().answer(sample, account_id=None, question="Why does this matter to BTX?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id})
    assert "FAA production oversight update" in response.content
    assert "Resolved organization: Boeing" in response.content
    assert "current SAMPLE commercial dataset" in response.content
    assert response.citation_links and response.context_used == {"event_id": event_id, "surface": "INTELLIGENCE", "account_id": "boeing"}
    assert any("No canonical facility association" in item for item in response.missingness)


def test_omni_selected_event_handles_unresolved_conflicting_evidence_without_guessing() -> None:
    sample = build_sample_environment()
    raw = RawSignal("controlled-unresolved", SignalKind.PRESS_RELEASE, "Controlled unresolved public event", "https://example.test/unresolved", NOW, None, "Unmapped program", EvidenceState.CONFLICTING, "Controlled unit fixture.")
    controlled = replace(sample, intelligence_events=(*sample.intelligence_events, raw))
    event_id = OmniOrchestrator._sample_event_records(controlled)[-1]["id"]
    response = OmniOrchestrator().answer(controlled, account_id=None, question="What happened here?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id})
    assert "Controlled unresolved public event" in response.content
    assert "unresolved to a canonical researched account" in response.content
    assert response.account_id == "" and response.context_used == {"event_id": event_id, "surface": "INTELLIGENCE"}
    assert "CONFLICTING" in response.content and any("Unmapped program" in item for item in response.missingness)


def test_omni_selected_event_preserves_non_event_queries_and_invalid_event_handling() -> None:
    sample = build_sample_environment()
    event_id = event_id_for(sample, "boeing")
    omni = OmniOrchestrator()
    cross_account = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id})
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id})
    invalid = omni.answer(sample, account_id=None, question="What happened here?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": "missing-event"})
    assert "Defense researched account(s) with open quotes" in cross_account.content and "FAA production oversight update" not in cross_account.content
    assert "curated public-company universe" in general.content and "FAA production oversight update" not in general.content
    assert "not available in the current canonical Monitor read model" in invalid.content
