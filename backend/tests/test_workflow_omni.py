from datetime import UTC, datetime

import pytest

from btx_omni.integrations.hubspot.contracts import (
    CrmProviderState,
    SampleHubSpotAdapter,
)
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.modules.work.service import WorkService, WorkStatus
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


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
