from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine

from btx_omni.domain.work import (
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
    Principal,
    PrincipalRole,
)
from btx_omni.integrations.hubspot.contracts import SampleHubSpotAdapter
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
    with pytest.raises(ActionConflictError):
        service.confirm_and_execute_crm_action(
            action.id, SampleHubSpotAdapter({}), principal=MANAGER, occurred_at=NOW
        )
    service.decide_approval(
        action.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW
    )
    assert service.confirm_and_execute_crm_action(
        action.id, SampleHubSpotAdapter({}), principal=MANAGER, occurred_at=NOW
    ).executed


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
