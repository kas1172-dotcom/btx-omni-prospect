from dataclasses import replace
from datetime import UTC, datetime

import pytest

from btx_omni.domain.common import EvidenceState
from btx_omni.integrations.hubspot.contracts import (
    CrmProviderState,
    SampleHubSpotAdapter,
)
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.assistant.orchestration import (
    AssistantProvenance,
    OmniOrchestrator,
)
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


def public_facility_id_for(sample, account_id: str) -> str:
    return next(item.id for item in sample.public_facilities if item.account_id == account_id)


def create_selected_work_item(*, account_id: str = "boeing", evidence_ids: tuple[str, ...] = ("FAA_BOEING",), summary: str = "Review Boeing public evidence"):
    service = WorkService()
    item = service.create(
        account_id=account_id,
        summary=summary,
        evidence_ids=evidence_ids,
        idempotency_key=f"omni-{summary}",
        actor_id="seller",
        occurred_at=NOW,
        priority="HIGH",
    )
    return service, item


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


def test_omni_routes_a_selected_researched_facility_without_geographic_inference() -> None:
    sample = build_sample_environment()
    facility_id = public_facility_id_for(sample, "boeing")
    response = OmniOrchestrator().answer(
        sample,
        account_id=None,
        question="Tell me about this facility.",
        observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": facility_id},
    )
    assert "Boeing headquarters" in response.content
    assert "Arlington, VA, US" in response.content
    assert "Canonical parent account: Boeing (boeing)" in response.content
    assert response.citation_links
    assert response.context_used == {"facility_id": facility_id, "surface": "MAP"}
    assert "proximity is not used" in response.content


def test_omni_routes_a_selected_btx_facility_without_customer_identity_or_sample_claim() -> None:
    sample = build_sample_environment()
    response = OmniOrchestrator().answer(
        sample,
        account_id=None,
        question="Tell me about this facility.",
        observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": "era-elk-grove"},
    )
    assert "Canonical BTX facility: ERA Elk Grove" in response.content
    assert "Canonical BTX business unit: ERA (era-industries)" in response.content
    assert response.account_id == "" and response.account_name is None
    assert response.context_used == {"facility_id": "era-elk-grove", "surface": "MAP"}
    assert "No customer or prospect account association is inferred" in response.content
    assert "SAMPLE commercial dataset" not in response.content


def test_omni_selected_facility_evidence_relevance_missing_and_conflicting_account_context() -> None:
    sample = build_sample_environment()
    facility_id = public_facility_id_for(sample, "boeing")
    omni = OmniOrchestrator()
    evidence = omni.answer(
        sample,
        account_id=None,
        question="What evidence supports this facility record?",
        observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": facility_id},
    )
    relevance = omni.answer(
        sample,
        account_id=None,
        question="Why does this facility matter?",
        observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": facility_id},
    )
    conflict = omni.answer(
        sample,
        account_id=None,
        question="Who owns this facility?",
        observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": facility_id, "selected_account_id": "lockheed-martin"},
    )
    assert evidence.citations and evidence.citation_links
    assert "facility score" in relevance.content and "current SAMPLE commercial dataset" in relevance.content
    assert relevance.context_used["account_id"] == "boeing"
    assert "does not match this facility's canonical parent account" in conflict.content
    assert any("conflicts" in item for item in conflict.missingness)
    assert conflict.context_used == {"facility_id": facility_id, "surface": "MAP"}


def test_omni_selected_facility_preserves_non_facility_queries_and_invalid_ids() -> None:
    sample = build_sample_environment()
    facility_id = public_facility_id_for(sample, "boeing")
    omni = OmniOrchestrator()
    cross_account = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW, context={"surface": "MAP", "selected_facility_id": facility_id})
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW, context={"surface": "MAP", "selected_facility_id": facility_id})
    invalid = omni.answer(sample, account_id=None, question="Tell me about this facility.", observed_at=NOW, context={"surface": "MAP", "selected_facility_id": "missing-facility"})
    assert "Defense researched account(s) with open quotes" in cross_account.content and "Boeing headquarters" not in cross_account.content
    assert "curated public-company universe" in general.content and "Boeing headquarters" not in general.content
    assert "can't resolve the selected facility" in invalid.content


def test_omni_routes_a_selected_work_item_with_stored_evidence_and_sample_boundary() -> None:
    sample = build_sample_environment()
    service, item = create_selected_work_item()
    response = OmniOrchestrator().answer(
        sample,
        account_id=None,
        question="Why was this created?",
        observed_at=NOW,
        context={"surface": "ACTIONS", "selected_action_id": item.id},
        work_items=service.list(),
    )
    assert item.summary in response.content
    assert "Canonical account: Boeing (boeing)" in response.content
    assert "Stored supporting evidence IDs: FAA_BOEING" in response.content
    assert "No canonical originating commercial-alert or rule ID" in response.content
    assert "current SAMPLE commercial dataset" in response.content
    assert response.recommended_action == item.summary
    assert response.context_used == {"action_id": item.id, "surface": "ACTIONS", "account_id": "boeing"}


def test_omni_selected_work_item_explains_linked_conflicting_evidence_and_review_scope() -> None:
    sample = build_sample_environment()
    raw = RawSignal("controlled-action-conflict", SignalKind.PRESS_RELEASE, "Controlled conflicting action evidence", "https://example.test/action-conflict", NOW, "Boeing", None, EvidenceState.CONFLICTING, "Controlled unit fixture.")
    controlled = replace(sample, intelligence_events=(*sample.intelligence_events, raw))
    event_record = OmniOrchestrator._sample_event_records(controlled)[-1]
    service, item = create_selected_work_item(evidence_ids=tuple(event_record["evidence_ids"]), summary="Review conflicting public evidence")
    response = OmniOrchestrator().answer(
        controlled,
        account_id=None,
        question="What should I review before acting?",
        observed_at=NOW,
        context={"surface": "ACTIONS", "selected_action_id": item.id},
        intelligence_events=(event_record,),
        work_items=service.list(),
    )
    assert "Controlled conflicting action evidence" in response.content
    assert "evidence state: CONFLICTING" in response.content
    assert "No additional checklist is inferred" in response.content
    assert any("CONFLICTING" in item for item in response.missingness)


def test_omni_selected_work_item_handles_next_step_conflicts_invalid_and_read_only_execution() -> None:
    sample = build_sample_environment()
    service, item = create_selected_work_item()
    omni = OmniOrchestrator()
    next_step = omni.answer(sample, account_id=None, question="What should I do next?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id, "selected_account_id": "lockheed-martin"}, work_items=service.list())
    outcome = omni.answer(sample, account_id=None, question="What would happen if I act on this?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=service.list())
    before = service.list()
    execution = omni.answer(sample, account_id=None, question="Go ahead and execute this action.", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=service.list())
    invalid = omni.answer(sample, account_id=None, question="Why was this created?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": "missing-work-item"}, work_items=service.list())
    assert f"stored governed next step is the work-item summary: {item.summary}" in next_step.content
    assert "does not match this work item's canonical account" in next_step.content
    assert any("conflicts" in item for item in next_step.missingness)
    assert "cannot simulate or execute a workflow transition" in outcome.content
    assert "did not execute, complete, dismiss, or update" in execution.content
    assert service.list() == before
    assert "can't resolve the selected action" in invalid.content


def test_omni_selected_work_item_preserves_non_action_queries_and_missing_event_association() -> None:
    sample = build_sample_environment()
    service, item = create_selected_work_item()
    omni = OmniOrchestrator()
    cross_account = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=service.list())
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=service.list())
    missing_account_service, missing_account_item = create_selected_work_item(account_id="unmapped-account", summary="Review unmapped action")
    missing_account = omni.answer(sample, account_id=None, question="What account is this for?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": missing_account_item.id}, work_items=missing_account_service.list())
    assert "Defense researched account(s) with open quotes" in cross_account.content and item.summary not in cross_account.content
    assert "curated public-company universe" in general.content and item.summary not in general.content
    assert "No canonical originating Intelligence event" in missing_account.content
    assert "No canonical researched account association" in missing_account.content


def test_omni_routes_selected_account_relationships_through_canonical_service() -> None:
    sample = build_sample_environment()
    response = OmniOrchestrator().answer(
        sample,
        account_id=None,
        question="How are we connected to this company?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"},
    )
    assert "Spirit AeroSystems --PARENT_CHILD--> Boeing" in response.content
    assert "BOEING_SPIRIT" in response.content
    assert response.context_used == {"surface": "ACCOUNT_DETAIL", "account_id": "spirit-aerosystems"}


def test_omni_relationship_routing_preserves_source_less_and_conflicting_evidence() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    source_less = omni.answer(
        sample,
        account_id=None,
        question="What evidence supports this relationship?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"},
    )
    parent = next(edge for edge in sample.relationship_edges if edge.id == "e001")
    conflicting = replace(sample, relationship_edges=tuple(replace(edge, evidence_state=EvidenceState.CONFLICTING) if edge.id == parent.id else edge for edge in sample.relationship_edges))
    unusable = omni.answer(
        conflicting,
        account_id=None,
        question="How are Spirit AeroSystems and Boeing connected?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "lockheed-martin"},
    )
    assert "GEOGRAPHIC_CLUSTER_REVERSE" in source_less.content
    assert "needs_validation" in source_less.content
    assert any("no attached relationship source IDs" in item for item in source_less.missingness)
    assert "PARENT_CHILD" in unusable.content and "unusable" in unusable.content
    assert any("conflicting evidence" in item for item in unusable.missingness)


def test_omni_relationship_routing_uses_explicit_pair_program_and_warm_path_context() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    pair = omni.answer(
        sample,
        account_id=None,
        question="How are Boeing and Spirit AeroSystems connected?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "lockheed-martin"},
    )
    programs = omni.answer(
        sample,
        account_id=None,
        question="What programs connect Boeing and Northrop Grumman?",
        observed_at=NOW,
        context={},
    )
    warm = omni.answer(
        sample,
        account_id=None,
        question="Which current customer gives us a route into this prospect?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"},
    )
    assert "Boeing --PARENT_CHILD_REVERSE--> Spirit AeroSystems" in pair.content
    assert pair.context_used["account_id"] == "boeing" and pair.context_used["related_account_id"] == "spirit-aerosystems"
    assert "F-35 Lightning II" in programs.content and "NASA Artemis" in programs.content
    assert "Boeing has current SAMPLE commercial context" in warm.content
    assert "not a guaranteed introduction" in warm.content


def test_omni_relationship_routing_handles_contacts_no_path_invalid_and_read_only_requests() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    contact = omni.answer(
        sample,
        account_id=None,
        question="Do we know anyone connected to this account?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"},
    )
    no_path = omni.answer(
        sample,
        account_id=None,
        question="How are Lockheed Martin and Anduril Industries connected?",
        observed_at=NOW,
        context={},
    )
    invalid = omni.answer(
        sample,
        account_id=None,
        question="How are we connected to this company?",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "not-real"},
    )
    unresolved_named = omni.answer(
        sample,
        account_id=None,
        question="How are Boeing and Not A Real Company connected?",
        observed_at=NOW,
        context={},
    )
    work, item = create_selected_work_item()
    before = work.list()
    readonly = omni.answer(
        sample,
        account_id=None,
        question="Create an introduction task through this relationship.",
        observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"},
        work_items=work.list(),
    )
    assert "current SAMPLE CRM dataset" in contact.content
    assert "don't have an evidence-backed relationship path" in no_path.content
    assert "need a canonical researched account" in invalid.content
    assert "can't resolve 'not a real company'" in unresolved_named.content
    assert "did not create an introduction task" in readonly.content
    assert work.list() == before and item in before


def test_omni_relationship_routing_preserves_account_and_unrelated_routes() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    cross_account = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW, context={"selected_account_id": "spirit-aerosystems"})
    score = omni.answer(sample, account_id="boeing", question="Why is this account attractive?", observed_at=NOW, context={"selected_account_id": "spirit-aerosystems"})
    named_account = omni.answer(sample, account_id=None, question="Tell me about Boeing.", observed_at=NOW, context={"selected_account_id": "spirit-aerosystems"})
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW, context={"selected_account_id": "spirit-aerosystems"})
    assert "Defense researched account(s) with open quotes" in cross_account.content
    assert "Account Attractiveness" in score.content
    assert "Deterministic governed answer for Boeing" in named_account.content
    assert "curated public-company universe" in general.content


def test_omni_screen_summaries_respect_today_and_accounts_visible_scope() -> None:
    sample = build_sample_environment()
    event = OmniOrchestrator._sample_event_records(sample)[0]
    work, item = create_selected_work_item()
    alert = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW, orders=sample.orders)[0]
    omni = OmniOrchestrator()
    today = omni.answer(
        sample,
        account_id=None,
        question="What matters most on this page?",
        observed_at=NOW,
        context={"surface": "TODAY", "visible_record_ids": [alert.id, event["id"], item.id]},
        intelligence_events=(event,),
        work_items=work.list(),
    )
    accounts = omni.answer(
        sample,
        account_id=None,
        question="What should I pay attention to here?",
        observed_at=NOW,
        context={"surface": "ACCOUNTS", "active_filters": {"market": "Defense"}, "visible_record_ids": ["boeing", "lockheed-martin"]},
    )
    assert alert.type.value in today.content and event["title"] in today.content and item.summary in today.content
    assert today.context_used == {"surface": "TODAY"}
    assert "Boeing" in accounts.content and "Lockheed Martin" in accounts.content
    assert "Northrop Grumman" not in accounts.content
    assert accounts.context_used == {"surface": "ACCOUNTS", "filters": {"market": "Defense"}}
    assert "current SAMPLE commercial dataset" in accounts.content


def test_omni_screen_summaries_use_selected_and_visible_canonical_context() -> None:
    sample = build_sample_environment()
    event_records = OmniOrchestrator._sample_event_records(sample)
    selected_event = event_id_for(sample, "boeing")
    work, item = create_selected_work_item()
    omni = OmniOrchestrator()
    account_detail = omni.answer(
        sample, account_id=None, question="Summarize this screen.", observed_at=NOW,
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "boeing"}, intelligence_events=event_records,
    )
    intelligence = omni.answer(
        sample, account_id=None, question="What are the most important things here?", observed_at=NOW,
        context={"surface": "INTELLIGENCE", "selected_event_id": selected_event, "active_filters": {"market": "Defense"}, "visible_record_ids": [selected_event]}, intelligence_events=event_records,
    )
    actions = omni.answer(
        sample, account_id=None, question="What should I focus on?", observed_at=NOW,
        context={"surface": "ACTIONS", "selected_action_id": item.id, "visible_record_ids": [item.id]}, work_items=work.list(),
    )
    assert "Account Detail summary for Boeing" in account_detail.content
    assert account_detail.context_used == {"surface": "ACCOUNT_DETAIL", "account_id": "boeing"}
    assert "Current Intelligence view" in intelligence.content and "Selected event:" in intelligence.content
    assert intelligence.context_used == {"surface": "INTELLIGENCE", "filters": {"market": "Defense"}, "event_id": selected_event}
    assert "Current Actions view" in actions.content and "Selected action:" in actions.content
    assert actions.context_used == {"surface": "ACTIONS", "action_id": item.id}


def test_omni_screen_summary_map_empty_invalid_and_specific_route_protection() -> None:
    sample = build_sample_environment()
    event_id = event_id_for(sample, "boeing")
    work, item = create_selected_work_item()
    facility_id = public_facility_id_for(sample, "boeing")
    omni = OmniOrchestrator()
    map_facility = omni.answer(
        sample, account_id=None, question="Give me the key takeaways from this page.", observed_at=NOW,
        context={"surface": "MAP", "selected_facility_id": facility_id},
    )
    map_empty = omni.answer(sample, account_id=None, question="What matters most on this page?", observed_at=NOW, context={"surface": "MAP"})
    invalid = omni.answer(sample, account_id=None, question="Summarize this screen.", observed_at=NOW, context={"surface": "ACCOUNTS", "visible_record_ids": ["unknown-account"]})
    event_question = omni.answer(sample, account_id=None, question="Why does this matter?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id}, intelligence_events=OmniOrchestrator._sample_event_records(sample))
    action_question = omni.answer(sample, account_id=None, question="Why was this created?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=work.list())
    relationship = omni.answer(sample, account_id=None, question="How are we connected to this company?", observed_at=NOW, context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"})
    cross_account = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW, context={"surface": "ACCOUNTS", "visible_record_ids": ["boeing"]})
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW, context={"surface": "ACCOUNTS", "visible_record_ids": ["boeing"]})
    assert "Canonical researched facility" in map_facility.content and map_facility.context_used["facility_id"] == facility_id
    assert "Map has no selected canonical account or facility" in map_empty.content
    assert "none of the supplied account IDs resolved" in invalid.content
    assert "Source-backed Intelligence event" in event_question.content
    assert item.summary in action_question.content
    assert "Spirit AeroSystems --PARENT_CHILD--> Boeing" in relationship.content
    assert "Defense researched account(s) with open quotes" in cross_account.content
    assert "curated public-company universe" in general.content


def test_omni_cross_account_score_ranking_uses_canonical_scores_filters_and_bounds() -> None:
    sample = build_sample_environment()
    omni = OmniOrchestrator()
    ranked = omni.answer(sample, account_id=None, question="Which accounts have the highest attractiveness scores?", observed_at=NOW)
    filtered = omni.answer(
        sample,
        account_id=None,
        question="Which accounts have the highest scores?",
        observed_at=NOW,
        context={"surface": "ACCOUNTS", "active_filters": {"market": "Defense"}},
    )
    unsupported = omni.answer(
        sample,
        account_id=None,
        question="Which accounts have the highest scores?",
        observed_at=NOW,
        context={"active_filters": {"market": "Robotics"}},
    )
    assert "Ranked by the existing canonical Account Attractiveness score" in ranked.content
    assert ranked.content.count("coverage") <= 5
    assert "Boeing" in filtered.content and "Intel" not in filtered.content
    assert filtered.context_used == {"filters": {"market": "Defense"}}
    assert "unsupported for this query" in unsupported.missingness[0]
    assert unsupported.context_used == {}


def test_omni_cross_account_work_intelligence_intersection_and_zero_results_are_read_only() -> None:
    sample = build_sample_environment()
    event_id = event_id_for(sample, "boeing")
    event = next(item for item in OmniOrchestrator._sample_event_records(sample) if item["id"] == event_id)
    work, item = create_selected_work_item()
    closed = work.create(account_id="lockheed-martin", summary="Closed work", evidence_ids=("ev-closed",), idempotency_key="closed-cross-account", actor_id="seller", occurred_at=NOW)
    work.transition(closed.id, WorkStatus.COMPLETED, actor_id="seller", occurred_at=NOW)
    omni = OmniOrchestrator()
    before = work.list()
    actions = omni.answer(sample, account_id=None, question="Which accounts have open actions?", observed_at=NOW, work_items=work.list())
    intelligence = omni.answer(sample, account_id=None, question="Which accounts have Intelligence?", observed_at=NOW, intelligence_events=(event,))
    intersection = omni.answer(sample, account_id=None, question="Which accounts have both recent Intelligence and open actions?", observed_at=NOW, intelligence_events=(event,), work_items=work.list())
    zero = omni.answer(sample, account_id=None, question="Which accounts have both recent Intelligence and open actions?", observed_at=NOW, intelligence_events=(event,), work_items=())
    assert item.summary in actions.content and "Closed work" not in actions.content
    assert event["title"] in intelligence.content and "source-backed" in intelligence.content
    assert "Boeing" in intersection.content and "does not establish" in intersection.content
    assert "No canonical accounts appear in both" in zero.content
    assert work.list() == before


def test_omni_cross_account_quotes_comparison_and_route_protection() -> None:
    sample = build_sample_environment()
    event_id = event_id_for(sample, "boeing")
    work, item = create_selected_work_item()
    omni = OmniOrchestrator()
    quotes = omni.answer(sample, account_id=None, question="Which Defense accounts have open quotes?", observed_at=NOW)
    history = omni.answer(sample, account_id=None, question="Where do we have quote history?", observed_at=NOW)
    comparison = omni.answer(sample, account_id=None, question="Compare Boeing and Lockheed Martin.", observed_at=NOW)
    unresolved = omni.answer(sample, account_id=None, question="Compare Boeing and Lockheed.", observed_at=NOW)
    event_route = omni.answer(sample, account_id=None, question="Why does this matter?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": event_id}, intelligence_events=OmniOrchestrator._sample_event_records(sample))
    action_route = omni.answer(sample, account_id=None, question="Why was this created?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=work.list())
    screen_route = omni.answer(sample, account_id=None, question="Summarize this screen.", observed_at=NOW, context={"surface": "ACCOUNTS", "visible_record_ids": ["boeing"]})
    general = omni.answer(sample, account_id=None, question="What is an RFQ?", observed_at=NOW)
    assert "Defense researched account(s) with open quotes" in quotes.content and "SAMPLE commercial dataset" in quotes.content
    assert quotes.citations == () and AssistantProvenance.DETERMINISTIC_DERIVATION in quotes.provenance
    assert "quote/RFQ history" in history.content
    assert "Canonical comparison: Boeing and Lockheed Martin" in comparison.content
    assert comparison.context_used == {"account_id": "boeing", "related_account_id": "lockheed-martin"}
    assert "exactly two canonical" in unresolved.content
    assert "Source-backed Intelligence event" in event_route.content
    assert item.summary in action_route.content
    assert "Current Accounts view" in screen_route.content
    assert "curated public-company universe" in general.content


def test_omni_conversation_event_precedence_continuity_and_staleness() -> None:
    sample = build_sample_environment()
    events = OmniOrchestrator._sample_event_records(sample)
    first_event = event_id_for(sample, "boeing")
    second_event = next(event["id"] for event in events if event["id"] != first_event)
    omni = OmniOrchestrator()
    first = omni.answer(sample, account_id=None, question="Why does this matter?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": first_event}, intelligence_events=events)
    continued = omni.answer(sample, account_id=None, question="Which account is it tied to?", observed_at=NOW, context={"surface": "ACCOUNTS", "conversation_referent": first.conversation_referent}, intelligence_events=events)
    superseded = omni.answer(sample, account_id=None, question="Why is this important?", observed_at=NOW, context={"surface": "INTELLIGENCE", "selected_event_id": second_event, "conversation_referent": first.conversation_referent}, intelligence_events=events)
    stale = omni.answer(sample, account_id=None, question="Which account is it tied to?", observed_at=NOW, context={"conversation_referent": {"event_id": "missing-event", "route": "EVENT"}}, intelligence_events=events)
    assert first.conversation_referent == {"event_id": first_event, "account_id": "boeing", "route": "EVENT"}
    assert "Resolved organization: Boeing" in continued.content and continued.context_used["context_source"] == "conversation"
    assert superseded.context_used["event_id"] == second_event and superseded.context_used.get("context_source") is None
    assert "no longer resolves" in stale.content


def test_omni_conversation_facility_action_account_and_cleared_screen_context() -> None:
    sample = build_sample_environment()
    facility_id = public_facility_id_for(sample, "boeing")
    work, item = create_selected_work_item()
    omni = OmniOrchestrator()
    facility = omni.answer(sample, account_id=None, question="Tell me about this facility.", observed_at=NOW, context={"surface": "MAP", "selected_facility_id": facility_id})
    owned = omni.answer(sample, account_id=None, question="Which account owns it?", observed_at=NOW, context={"surface": "ACCOUNTS", "conversation_referent": facility.conversation_referent})
    screen = omni.answer(sample, account_id=None, question="Summarize this screen.", observed_at=NOW, context={"surface": "ACCOUNTS", "visible_record_ids": ["lockheed-martin"], "conversation_referent": facility.conversation_referent})
    action = omni.answer(sample, account_id=None, question="Why was this created?", observed_at=NOW, context={"surface": "ACTIONS", "selected_action_id": item.id}, work_items=work.list())
    action_follow = omni.answer(sample, account_id=None, question="Which account is it for?", observed_at=NOW, context={"conversation_referent": action.conversation_referent}, work_items=work.list())
    account = omni.answer(sample, account_id=None, question="Tell me about Boeing.", observed_at=NOW)
    account_follow = omni.answer(sample, account_id=None, question="Does it have open actions?", observed_at=NOW, context={"conversation_referent": account.conversation_referent}, work_items=work.list())
    intelligence_follow = omni.answer(sample, account_id=None, question="Any Intelligence?", observed_at=NOW, context={"conversation_referent": account_follow.conversation_referent}, work_items=work.list())
    assert "Canonical parent account: Boeing" in owned.content and owned.context_used["context_source"] == "conversation"
    assert "Current Accounts view" in screen.content and "Boeing headquarters" not in screen.content
    assert "Canonical account: Boeing" in action_follow.content and action_follow.context_used["context_source"] == "conversation"
    assert "Canonical account follow-up for Boeing" in account_follow.content and "Current open governed work items: 1" in account_follow.content
    assert "Canonical account follow-up for Boeing" in intelligence_follow.content and "source-backed Intelligence" in intelligence_follow.content


def test_omni_conversation_comparison_relationship_and_ambiguity_are_bounded() -> None:
    sample = build_sample_environment()
    work, _item = create_selected_work_item()
    omni = OmniOrchestrator()
    comparison = omni.answer(sample, account_id=None, question="Compare Boeing and Lockheed Martin.", observed_at=NOW)
    score = omni.answer(sample, account_id=None, question="Which one has the higher score?", observed_at=NOW, context={"conversation_referent": comparison.conversation_referent}, work_items=work.list())
    actions = omni.answer(sample, account_id=None, question="Which one has more open actions?", observed_at=NOW, context={"conversation_referent": comparison.conversation_referent}, work_items=work.list())
    explicit = omni.answer(sample, account_id=None, question="Tell me about Northrop Grumman.", observed_at=NOW, context={"conversation_referent": comparison.conversation_referent})
    ambiguous = omni.answer(sample, account_id=None, question="What about the other one?", observed_at=NOW, context={"conversation_referent": comparison.conversation_referent})
    other = omni.answer(sample, account_id=None, question="What about the other one?", observed_at=NOW, context={"conversation_referent": {"account_id": "boeing", "comparison_account_ids": ["boeing", "lockheed-martin"], "route": "COMPARISON"}})
    relationship = omni.answer(sample, account_id=None, question="How are we connected to this company?", observed_at=NOW, context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spirit-aerosystems"})
    warmer = omni.answer(sample, account_id=None, question="Is there a warmer path?", observed_at=NOW, context={"conversation_referent": relationship.conversation_referent})
    global_query = omni.answer(sample, account_id=None, question="Which Defense accounts have the highest scores?", observed_at=NOW, context={"conversation_referent": comparison.conversation_referent})
    assert comparison.conversation_referent == {"comparison_account_ids": ["boeing", "lockheed-martin"], "route": "COMPARISON"}
    assert "attractiveness-score dimension" in score.content and score.context_used["context_source"] == "conversation"
    assert "open governed work item" in actions.content and actions.context_used["context_source"] == "conversation"
    assert "Deterministic governed answer for Northrop Grumman" in explicit.content
    assert "can't determine a unique conversational referent" in ambiguous.content
    assert "Deterministic governed answer for Lockheed Martin" in other.content and other.context_used["context_source"] == "conversation"
    assert relationship.conversation_referent["relationship_account_ids"] == ["spirit-aerosystems"]
    assert "Canonical relationship path" in warmer.content and warmer.context_used["context_source"] == "conversation"
    assert "Ranked by the existing canonical" in global_query.content and global_query.conversation_referent is None
