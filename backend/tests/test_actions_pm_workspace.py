from datetime import date

import pytest
from test_actions_v2 import MANAGER, NOW, OTHER, SELLER, durable_service

from btx_omni.domain.work import ActionStatus, ApprovalStatus
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    ActionNotFoundError,
    WorkService,
)
from btx_omni.persistence.actions import SqlActionRepository


def task(service, **kwargs):
    return service.create(account_id=None, title="Personal review", principal=SELLER, occurred_at=NOW, **kwargs)


@pytest.mark.parametrize("previous", [ActionStatus.OPEN, ActionStatus.IN_PROGRESS])
def test_cancel_persists_exact_restore_and_audits_reopen(tmp_path, previous):
    service = durable_service(tmp_path)
    action = task(service)
    if previous is ActionStatus.IN_PROGRESS:
        action = service.transition(action.id, previous, principal=SELLER, occurred_at=NOW)
    canceled = service.transition(action.id, ActionStatus.CANCELED, principal=SELLER, occurred_at=NOW, expected_version=action.version)
    restarted = WorkService(SqlActionRepository(service.repository.engine))
    assert restarted.get(action.id).allowed_transitions == (previous,)
    reopened = restarted.transition(action.id, previous, principal=SELLER, occurred_at=NOW, expected_version=canceled.version)
    assert reopened.status == previous and reopened.canceled_at is None
    assert restarted.audit(action.id)[-1].metadata['before'] == 'CANCELED'


def test_subtask_crud_soft_undo_revision_idempotency_and_single_level(tmp_path):
    service = durable_service(tmp_path)
    action = task(service)
    args = {'principal': SELLER, 'occurred_at': NOW, 'expected_version': action.version, 'idempotency_key': 'add-child-1', 'title': 'Draft review'}
    added = service.change_subtask(action.id, **args)
    child = added.subtasks[0]
    assert child.owner_id is None and not child.done and child.parent_id == action.id
    assert service.change_subtask(action.id, **args) == added
    with pytest.raises(ActionConflictError):
        service.change_subtask(action.id, **{**args, 'title': 'Different request'})
    with pytest.raises(ActionConflictError):
        service.change_subtask(action.id, **{**args, 'idempotency_key': 'stale-key'})
    with pytest.raises(ActionNotFoundError):
        service.change_subtask(child.id, **args)
    with pytest.raises(ValueError, match='one level'):
        service.change_subtask(action.id, **{**args, 'idempotency_key': 'nested-key', 'parent_id': child.id})
    current = added
    for index, change in enumerate([{'title': 'Renamed'}, {'done': True}, {'removed': True}, {'removed': False}]):
        current = service.change_subtask(action.id, subtask_id=child.id, principal=SELLER, occurred_at=NOW,
                                         expected_version=current.version, idempotency_key=f'edit-child-{index}', **change)
    persisted = WorkService(SqlActionRepository(service.repository.engine)).get(action.id)
    assert persisted.subtasks[0].title == 'Renamed' and persisted.subtasks[0].done and not persisted.subtasks[0].removed
    assert len([event for event in service.audit(action.id) if event.event == 'SUBTASK_CHANGED']) == 5


def test_completion_requires_explicit_subtask_consent_and_approval(tmp_path):
    service = durable_service(tmp_path)
    action = task(service, approval_required=True)
    action = service.change_subtask(action.id, principal=SELLER, occurred_at=NOW, expected_version=action.version,
                                    idempotency_key='complete-child-1', title='Open child')
    with pytest.raises(ActionConflictError, match='Approval'):
        service.transition(action.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW, complete_open_subtasks=True)
    service.request_approval(action.id, principal=SELLER, occurred_at=NOW, expected_version=action.version)
    service.decide_approval(action.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW)
    with pytest.raises(ActionConflictError, match='subtasks'):
        service.transition(action.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW)
    completed = service.transition(action.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW, complete_open_subtasks=True)
    assert completed.subtasks[0].done
    assert service.audit(action.id)[-1].metadata['completed_subtasks'] == [completed.subtasks[0].id]
    reopened = service.transition(action.id, ActionStatus.IN_PROGRESS, principal=SELLER, occurred_at=NOW)
    assert reopened.completed_at is None


@pytest.mark.parametrize('decision', [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CHANGES_REQUESTED])
def test_owner_requests_manager_decides_and_negative_decisions_preserve_active_work(decision):
    service = WorkService()
    action = task(service)
    with pytest.raises(ActionForbiddenError):
        service.request_approval(action.id, principal=OTHER, occurred_at=NOW, expected_version=action.version)
    requested = service.request_approval(action.id, principal=SELLER, occurred_at=NOW, expected_version=action.version)
    assert requested.approval_status is ApprovalStatus.REQUESTED
    with pytest.raises(ActionForbiddenError):
        service.decide_approval(action.id, decision, principal=SELLER, occurred_at=NOW)
    if decision != ApprovalStatus.APPROVED:
        with pytest.raises(ActionConflictError, match='comment'):
            service.decide_approval(action.id, decision, principal=MANAGER, occurred_at=NOW)
    decided = service.decide_approval(action.id, decision, principal=MANAGER, occurred_at=NOW, comment='Check the supporting evidence')
    assert decided in service.list(SELLER)
    assert decided.status == (ActionStatus.IN_PROGRESS if decision == ApprovalStatus.CHANGES_REQUESTED else ActionStatus.OPEN)
    event = service.audit(action.id)[-1]
    assert event.actor_id == MANAGER.user_id and event.occurred_at == NOW and event.metadata['comment'] == decided.approval_comment


def test_manager_cannot_decide_own_request():
    service = WorkService()
    action = service.create(account_id=None, title='Manager task', principal=MANAGER, occurred_at=NOW)
    service.request_approval(action.id, principal=MANAGER, occurred_at=NOW, expected_version=action.version)
    with pytest.raises(ActionForbiddenError, match='own approval'):
        service.decide_approval(action.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW)


def test_due_order_and_injected_overdue_date():
    service = WorkService()
    unscheduled = task(service, idempotency_key='unscheduled')
    later = task(service, idempotency_key='later', due_date=date(2026, 10, 1))
    earlier = task(service, idempotency_key='earlier', due_date=date(2026, 9, 1))
    last_date = task(service, idempotency_key='last-date', due_date=date.max)
    assert service.list() == (earlier, later, last_date, unscheduled)
    assert not earlier.is_overdue(date(2026, 9, 1))
    assert earlier.is_overdue(date(2026, 9, 2))
    completed = service.transition(earlier.id, ActionStatus.COMPLETED, principal=SELLER, occurred_at=NOW)
    assert not completed.is_overdue(date(2026, 9, 2))


def test_required_fields_cannot_be_cleared_and_closed_approval_cannot_reopen_work():
    service = WorkService()
    action = task(service, approval_required=True)
    for changes in ({'title': None}, {'title': ' '}, {'priority': None}):
        with pytest.raises(ValueError):
            service.edit(action.id, principal=SELLER, occurred_at=NOW, **changes)
    canceled = service.transition(action.id, ActionStatus.CANCELED, principal=SELLER, occurred_at=NOW)
    with pytest.raises(ActionConflictError, match='Reopen'):
        service.decide_approval(action.id, ApprovalStatus.CHANGES_REQUESTED, principal=MANAGER, occurred_at=NOW, comment='More evidence')
    assert service.get(action.id) == canceled


def test_creation_replay_accepts_added_navigation_context_but_never_changed_evidence():
    service = WorkService()
    request = {'account_id': 'boeing', 'title': 'Original', 'principal': SELLER, 'occurred_at': NOW,
               'idempotency_key': 'existing-intelligence-key', 'context_referents': (('intelligence_event', 'event-1'),)}
    original = service.create(**request)
    replay = service.create(**{**request, 'context_referents': (*request['context_referents'], ('source_screen', 'Intelligence'))})
    assert replay == original
    with pytest.raises(ActionConflictError):
        service.create(**{**request, 'evidence_ids': ('different-evidence',)})
