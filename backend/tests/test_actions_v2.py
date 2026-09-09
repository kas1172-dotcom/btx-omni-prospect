from datetime import UTC, date, datetime
from hashlib import sha256

import pytest
from sqlalchemy import create_engine

from btx_omni.domain.work import (
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
    Principal,
    PrincipalRole,
)
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    WorkService,
)
from btx_omni.persistence.actions import SqlActionRepository
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 8, 31, tzinfo=UTC)
SELLER = Principal("seller-1", "Seller", PrincipalRole.SALESPERSON)
OTHER = Principal("seller-2", "Other Seller", PrincipalRole.SALESPERSON)
MANAGER = Principal("manager-1", "Manager", PrincipalRole.MANAGER)


def durable_service(tmp_path) -> WorkService:
    engine = create_engine(f"sqlite:///{tmp_path / 'actions.db'}")
    metadata.create_all(engine)
    return WorkService(SqlActionRepository(engine))


def test_action_is_durable_across_service_restart_with_structured_history(
    tmp_path,
) -> None:
    service = durable_service(tmp_path)
    action = service.create(
        account_id="boeing",
        title="Review opportunity",
        description="Use governed evidence",
        priority=ActionPriority.HIGH,
        due_date=date(2026, 9, 4),
        evidence_ids=("FAA_BOEING",),
        principal=SELLER,
        occurred_at=NOW,
    )
    restarted = WorkService(SqlActionRepository(service.repository.engine))
    persisted = restarted.get(action.id)
    assert persisted.title == "Review opportunity" and persisted.due_date == date(
        2026, 9, 4
    )
    assert restarted.audit(action.id)[0].metadata == {"status": "OPEN"}


def test_action_state_machine_rejects_arbitrary_or_terminal_transitions() -> None:
    service = WorkService()
    action = service.create(
        account_id="boeing", title="Prepare review", principal=SELLER, occurred_at=NOW
    )
    with pytest.raises(ActionConflictError):
        service.transition(
            action.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW
        )
    active = service.transition(
        action.id, ActionStatus.IN_PROGRESS, principal=SELLER, occurred_at=NOW
    )
    completed = service.transition(
        active.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW
    )
    with pytest.raises(ActionConflictError):
        service.transition(
            completed.id, ActionStatus.OPEN, principal=SELLER, occurred_at=NOW
        )


def test_assignment_and_approval_are_manager_authorized_and_orthogonal() -> None:
    service = WorkService()
    action = service.create(
        account_id="boeing",
        title="Governed CRM follow-up",
        approval_required=True,
        principal=SELLER,
        occurred_at=NOW,
    )
    with pytest.raises(ActionForbiddenError):
        service.edit(action.id, principal=SELLER, occurred_at=NOW, owner_id="seller-2")
    assigned = service.edit(
        action.id, principal=MANAGER, occurred_at=NOW, owner_id="seller-2"
    )
    with pytest.raises(ActionForbiddenError):
        service.decide_approval(
            action.id, ApprovalStatus.APPROVED, principal=SELLER, occurred_at=NOW
        )
    approved = service.decide_approval(
        action.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW
    )
    assert (
        assigned.owner_id == "seller-2"
        and approved.approval_status is ApprovalStatus.APPROVED
    )
    assert approved.status is ActionStatus.OPEN


def test_salesperson_scope_and_external_write_boundary_are_enforced() -> None:
    from test_crm_proposals import adapter

    from btx_omni.modules.work.crm_proposals import CrmProposalWorkflow

    service = WorkService()
    action = service.create(
        account_id="boeing",
        title="Manager-owned",
        owner_id="seller-2",
        approval_required=True,
        principal=MANAGER,
        occurred_at=NOW,
    )
    with pytest.raises(ActionForbiddenError):
        service.edit(
            action.id, principal=SELLER, occurred_at=NOW, title="Impersonated edit"
        )
    workflow = CrmProposalWorkflow(service, adapter(), commercial_revision='test-revision')
    with pytest.raises(ActionConflictError):
        workflow.execute_sample(action.id, 'not-previewed', expected_decision_id='missing', idempotency_key='not-approved', principal=MANAGER, now=NOW)
    service.decide_approval(
        action.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW
    )
    proposal = workflow.preview(action.id, expected_version=service.get(action.id).version, principal=MANAGER, now=NOW)
    with pytest.raises(ActionConflictError, match='approval'):
        workflow.execute_sample(action.id, proposal['proposal_id'], expected_decision_id='missing', idempotency_key='work-only-approved', principal=MANAGER, now=NOW)
    decision = workflow.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=MANAGER, now=NOW)
    outcome = workflow.execute_sample(action.id, proposal['proposal_id'], expected_decision_id=decision['decision_id'], idempotency_key='exact-approved-1', principal=MANAGER, now=NOW)
    assert outcome['status'] == 'SAMPLE_COMPLETED' and not outcome['external_write']


def test_suggestion_conversion_is_idempotent_and_dismissal_is_separate() -> None:
    service = WorkService()
    first = service.create(
        account_id="boeing",
        title="Review evidence",
        source_suggestion_id="suggestion-1",
        evidence_ids=("ev-1",),
        principal=SELLER,
        occurred_at=NOW,
    )
    replay = service.create(
        account_id="boeing",
        title="Changed title",
        source_suggestion_id="suggestion-1",
        evidence_ids=("ev-1",),
        principal=SELLER,
        occurred_at=NOW,
    )
    service.dismiss_suggestion("suggestion-2", principal=SELLER, occurred_at=NOW)
    assert replay.id == first.id and replay.title == first.title
    assert service.dismissed_suggestions() == frozenset({"suggestion-2"})
    assert first.status is ActionStatus.OPEN


def test_retry_keys_are_scoped_to_creator_and_account_and_payload(tmp_path) -> None:
    service = durable_service(tmp_path)
    request = {"account_id": "boeing", "title": "Review", "principal": SELLER,
               "occurred_at": NOW, "idempotency_key": "same-client-key"}
    first = service.create(**request)
    other = service.create(**{**request, "principal": OTHER})
    other_account = service.create(**{**request, "account_id": "kla"})
    assert len({first.id, other.id, other_account.id}) == 3
    restarted = WorkService(SqlActionRepository(service.repository.engine))
    assert restarted.create(**request) == first
    with pytest.raises(ActionConflictError, match="original proposal"):
        restarted.create(**{**request, "title": "Different commitment"})
    edited = restarted.edit(first.id, principal=SELLER, occurred_at=NOW,
                            title="Reviewed title", expected_version=1)
    assert restarted.create(**request) == edited
    assert [event.event for event in restarted.audit(first.id)] == ["CREATED", "EDITED"]


def test_legacy_retry_preserves_identity_without_disclosing_other_work() -> None:
    from dataclasses import replace

    service = WorkService()
    original = service.create(account_id="boeing", title="Review", principal=SELLER,
                              occurred_at=NOW)
    legacy_id = "action-" + sha256(b"legacy-key").hexdigest()[:20]
    legacy = replace(original, id=legacy_id)
    service.repository.items = {legacy_id: legacy}
    service.repository.events = []
    request = {"account_id": "boeing", "title": "Review", "principal": SELLER,
               "occurred_at": NOW, "idempotency_key": "legacy-key"}
    assert service.create(**request).id == legacy_id
    assert service.create(**{**request, "principal": OTHER}).id != legacy_id
    with pytest.raises(ActionConflictError):
        service.create(**{**request, "title": "Overwrite"})


def test_suggestion_retry_authorizes_before_return_and_checks_account() -> None:
    service = WorkService()
    request = {"account_id": "boeing", "title": "Review", "principal": SELLER,
               "occurred_at": NOW, "source_suggestion_id": "scoped-suggestion"}
    first = service.create(**request)
    with pytest.raises(ActionForbiddenError):
        service.create(**{**request, "principal": OTHER})
    with pytest.raises(ActionConflictError):
        service.create(**{**request, "account_id": "kla"})
    assert service.create(**request) == first
