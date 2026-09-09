from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from test_actions_v2 import MANAGER, OTHER, SELLER

from btx_omni.domain.work import ActionStatus
from btx_omni.integrations.hubspot.contracts import (
    CrmAccountContext,
    CrmProviderState,
    SampleHubSpotAdapter,
)
from btx_omni.modules.work.crm_proposals import CrmProposalWorkflow
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    WorkService,
)
from btx_omni.persistence.actions import SqlActionRepository
from btx_omni.persistence.models import metadata
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 9, 8, 13, tzinfo=UTC)


def adapter(account='boeing'):
    company = next(item for item in build_sample_environment().crm_companies if item.account_id == account)
    return SampleHubSpotAdapter({account: CrmAccountContext(company, (), (), (), (), CrmProviderState.AVAILABLE)})


@pytest.fixture
def flow(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "crm.db"}')
    metadata.create_all(engine)
    work = WorkService(SqlActionRepository(engine))
    action = work.create(account_id='boeing', title='Review delivery recovery, do not commit capacity',
                         principal=SELLER, occurred_at=NOW)
    yield CrmProposalWorkflow(work, adapter(), commercial_revision='revision-1'), action
    engine.dispose()


def approved(flow, action):
    proposal = flow.preview(action.id, expected_version=action.version, principal=SELLER, now=NOW)
    decision = flow.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=MANAGER, now=NOW)
    return proposal, decision


def test_durable_proposal_exact_payload_and_approved_sample_replay_never_external(flow):
    workflow, action = flow
    proposal, decision = approved(workflow, action)
    assert proposal['payload']['title'] == action.title and proposal['payload']['due_date'] is None
    assert proposal['destination'] == 'LOCAL_SAMPLE_ONLY' and proposal['mapping']['portal_id'] is None
    assert workflow.preview(action.id, expected_version=action.version, principal=SELLER, now=NOW) == proposal
    restarted = CrmProposalWorkflow(WorkService(SqlActionRepository(workflow.work.repository.engine)), adapter(), commercial_revision='revision-1')
    args = {'expected_decision_id': decision['decision_id'], 'idempotency_key': 'sample-attempt-1', 'principal': MANAGER, 'now': NOW}
    result = restarted.execute_sample(action.id, proposal['proposal_id'], **args)
    assert result['status'] == 'SAMPLE_COMPLETED' and not result['external_write']
    assert restarted.execute_sample(action.id, proposal['proposal_id'], **args)['attempt_id'] == result['attempt_id']
    assert restarted.execute_sample(action.id, proposal['proposal_id'], **{**args, 'idempotency_key': 'another-click-2'})['replayed']
    events = restarted.inspect(action.id, principal=SELLER)['events']
    assert [event['kind'] for event in events] == ['CRM_PROPOSED', 'CRM_DECIDED', 'CRM_SAMPLE_ATTEMPT']
    assert restarted.work.get(action.id) == action
    assert all('request_key_hash' not in event['data'] for event in events)


def test_proposal_permissions_mapping_staleness_and_approval_are_enforced(flow):
    workflow, action = flow
    with pytest.raises(ActionForbiddenError):
        workflow.preview(action.id, expected_version=1, principal=OTHER, now=NOW)
    proposal = workflow.preview(action.id, expected_version=1, principal=SELLER, now=NOW)
    with pytest.raises(ActionForbiddenError):
        workflow.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=SELLER, now=NOW)
    with pytest.raises(ActionConflictError, match='approval'):
        workflow.execute_sample(action.id, proposal['proposal_id'], expected_decision_id='missing', idempotency_key='no-approval', principal=MANAGER, now=NOW)
    changed = CrmProposalWorkflow(workflow.work, adapter(), commercial_revision='revision-2')
    with pytest.raises(ActionConflictError, match='changed'):
        changed.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=MANAGER, now=NOW)
    missing = CrmProposalWorkflow(workflow.work, SampleHubSpotAdapter({}), commercial_revision='revision-1')
    unmapped = missing.preview(action.id, expected_version=1, principal=SELLER, now=NOW)
    assert unmapped['blockers'] and unmapped['mapping']['company_id'] is None
    with pytest.raises(ActionConflictError, match='mapping'):
        missing.decide(action.id, unmapped['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=MANAGER, now=NOW)
    workflow.work.edit(action.id, title='Changed after preview', principal=SELLER, occurred_at=NOW, expected_version=1)
    with pytest.raises(ActionConflictError, match='changed'):
        workflow.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=None, principal=MANAGER, now=NOW)


def test_rejected_approval_late_retry_and_failed_attempt_recovery_are_truthful(flow, monkeypatch):
    workflow, action = flow
    proposal, decision = approved(workflow, action)
    original = SampleHubSpotAdapter.execute_action
    monkeypatch.setattr(SampleHubSpotAdapter, 'execute_action', lambda self, preview: replace(preview, unavailable_reason='Explicit test provider outage'))
    args = {'expected_decision_id': decision['decision_id'], 'idempotency_key': 'failed-request-1', 'principal': MANAGER, 'now': NOW}
    failed = workflow.execute_sample(action.id, proposal['proposal_id'], **args)
    assert failed['status'] == 'SAMPLE_FAILED' and not failed['external_write']
    monkeypatch.setattr(SampleHubSpotAdapter, 'execute_action', original)
    assert workflow.execute_sample(action.id, proposal['proposal_id'], **args)['status'] == 'SAMPLE_FAILED'
    rejected = workflow.decide(action.id, proposal['proposal_id'], decision='REJECTED', expected_decision_id=decision['decision_id'], principal=MANAGER, now=NOW)
    with pytest.raises(ActionConflictError, match='approval'):
        workflow.execute_sample(action.id, proposal['proposal_id'], **{**args, 'idempotency_key': 'new-attempt-2'})
    approval = workflow.decide(action.id, proposal['proposal_id'], decision='APPROVED', expected_decision_id=rejected['decision_id'], principal=MANAGER, now=NOW)
    succeeded = workflow.execute_sample(action.id, proposal['proposal_id'], **{**args, 'expected_decision_id': approval['decision_id'], 'idempotency_key': 'new-attempt-3'})
    assert succeeded['status'] == 'SAMPLE_COMPLETED'
    with pytest.raises(ActionConflictError, match='different'):
        workflow.execute_sample(action.id, proposal['proposal_id'], **{**args, 'expected_decision_id': approval['decision_id']})
    workflow.work.transition(action.id, ActionStatus.CANCELED, principal=SELLER, occurred_at=NOW)
    assert workflow.execute_sample(action.id, proposal['proposal_id'], **args)['status'] == 'SAMPLE_FAILED'
    with pytest.raises(ActionConflictError, match='changed'):
        workflow.execute_sample(action.id, proposal['proposal_id'], **{**args, 'idempotency_key': 'closed-new-4'})


def test_live_adapter_cannot_be_invoked_by_sample_workflow(flow):
    workflow, action = flow
    class UnapprovedPort:
        def account_context(self, account_id):
            pytest.fail('An unauthorized external adapter must never be invoked.')
    live = CrmProposalWorkflow(workflow.work, UnapprovedPort(), commercial_revision='revision-1')
    with pytest.raises(ActionConflictError, match='not authorized'):
        live.preview(action.id, expected_version=1, principal=SELLER, now=NOW)


def test_concurrent_sample_retry_records_one_immutable_attempt(flow):
    from concurrent.futures import ThreadPoolExecutor

    workflow, action = flow
    proposal, decision = approved(workflow, action)
    def execute(_):
        return workflow.execute_sample(action.id, proposal['proposal_id'], expected_decision_id=decision['decision_id'],
                                       idempotency_key='concurrent-request', principal=MANAGER, now=NOW)
    with ThreadPoolExecutor(max_workers=4) as executor:
        attempts = list(executor.map(execute, range(6)))
    assert len({item['attempt_id'] for item in attempts}) == 1
    assert len([event for event in workflow.inspect(action.id, principal=SELLER)['events'] if event['kind'] == 'CRM_SAMPLE_ATTEMPT']) == 1


def test_crm_api_exact_destination_approval_authorization_and_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from test_hosted_sessions import _production_app, _sign_in

    url = f'sqlite:///{tmp_path / "api-crm.db"}'
    metadata.create_all(create_engine(url))
    seller = _production_app(monkeypatch, database_url=url)
    assert seller.get('/api/actions/missing/crm-proposals').status_code == 401
    session = _sign_in(seller, 'hosted-seller-access')
    headers = {'X-CSRF-Token': session['csrf_token']}
    action = seller.post('/api/actions', headers=headers, json={'account_id': 'boeing', 'title': 'Review constrained delivery', 'idempotency_key': 'crm-api-action'}).json()
    root = f"/api/actions/{action['id']}"
    assert seller.post(root + '/crm-preview', json={'expected_version': 1}).status_code == 403
    prepared = seller.post(root + '/crm-preview', headers=headers, json={'expected_version': 1})
    assert prepared.status_code == 200, prepared.text
    proposal = prepared.json()
    assert proposal['destination'] == 'LOCAL_SAMPLE_ONLY' and proposal['mapping']['company_id']
    assert proposal['mapping']['account_id'] == 'boeing' and not proposal['external_write']
    body = {'proposal_id': proposal['proposal_id'], 'decision': 'APPROVED', 'expected_decision_id': None}
    assert seller.post(root + '/crm-proposal-decision', headers=headers, json=body).status_code == 403
    manager = TestClient(seller.app, base_url='https://backend.test')
    manager_session = _sign_in(manager, 'hosted-manager-access')
    manager_headers = {'X-CSRF-Token': manager_session['csrf_token']}
    decision = manager.post(root + '/crm-proposal-decision', headers=manager_headers, json=body).json()
    attempt = {'proposal_id': proposal['proposal_id'], 'expected_decision_id': decision['decision_id'], 'idempotency_key': 'api-crm-attempt'}
    assert seller.post(root + '/crm-execute?confirmed=true', headers=headers, json=attempt).status_code == 403
    assert manager.post(root + '/crm-execute', headers=manager_headers, json=attempt).status_code == 409
    result = manager.post(root + '/crm-execute?confirmed=true', headers=manager_headers, json=attempt)
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'SAMPLE_COMPLETED' and not result.json()['external_write']
    restarted = _production_app(monkeypatch, database_url=url)
    restarted_session = _sign_in(restarted, 'hosted-manager-access')
    recovered = restarted.post(root + '/crm-execute?confirmed=true', headers={'X-CSRF-Token': restarted_session['csrf_token']}, json=attempt)
    assert recovered.json()['attempt_id'] == result.json()['attempt_id'] and recovered.json()['replayed']
    history = restarted.get(root + '/crm-proposals')
    assert history.headers['cache-control'] == 'private, no-store'
    assert len(history.json()['events']) == 3
    assert restarted.get(root).json()['status'] == 'OPEN'
