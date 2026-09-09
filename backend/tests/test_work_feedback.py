from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select

from btx_omni.persistence.models import metadata
from btx_omni.persistence.work_feedback import (
    FeedbackConflict,
    SuggestionFeedbackRepository,
    work_suggestion_feedback,
)

NOW = datetime(2026, 9, 8, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'feedback.db'}")
    metadata.create_all(engine)
    return SuggestionFeedbackRepository(engine)


def write(repository, **changes):
    return repository.append(**dict(user_id='seller', suggestion_id='suggestion-1', account_id='boeing',
                                    reason='NOT_RELEVANT', note='', now=NOW, idempotency_key='request-1',
                                    expected_feedback_id=None, **changes))


def test_private_restart_undo_replay_does_not_reapply_and_history_is_immutable(repository):
    first = write(repository)
    restarted = SuggestionFeedbackRepository(repository.engine)
    assert restarted.current('seller', ('suggestion-1',), now=NOW)['suggestion-1']['hidden']
    assert restarted.current('other', ('suggestion-1',), now=NOW) == {}
    assert restarted.current('manager', ('suggestion-1',), now=NOW) == {}
    undo = restarted.append(user_id='seller', suggestion_id='suggestion-1', account_id='boeing',
                            reason='UNDO', note='', now=NOW, idempotency_key='request-undo', expected_feedback_id=first['id'])
    assert write(restarted)['id'] == first['id']
    current = restarted.current('seller', ('suggestion-1',), now=NOW)['suggestion-1']
    assert not current['hidden'] and current['id'] == undo['id'] and current['version'] == 2
    with repository.engine.connect() as connection:
        rows = connection.execute(select(work_suggestion_feedback).order_by(work_suggestion_feedback.c.version)).mappings().all()
    assert len(rows) == 2 and rows[0]['reason'] == 'NOT_RELEVANT' and rows[1]['previous_feedback_id'] == first['id']


def test_conflicting_replay_stale_version_and_foreign_undo_are_rejected(repository):
    first = write(repository)
    base = {'user_id': 'seller', 'suggestion_id': 'suggestion-1', 'account_id': 'boeing', 'reason': 'NOT_RELEVANT', 'note': '', 'now': NOW,
            'idempotency_key': 'request-1', 'expected_feedback_id': None}
    for patch in ({'note': 'different'}, {'idempotency_key': 'new-request'},
                  {'user_id': 'other', 'reason': 'UNDO', 'expected_feedback_id': first['id']}):
        with pytest.raises(FeedbackConflict):
            repository.append(**{**base, **patch})


def test_snooze_expiry_and_late_identical_retry_preserve_original_receipt(repository):
    args = {'user_id': 'seller', 'suggestion_id': 'suggestion-1', 'account_id': 'boeing', 'reason': 'SNOOZE', 'note': '', 'now': NOW,
            'idempotency_key': 'snooze-1', 'expected_feedback_id': None, 'snooze_until': NOW + timedelta(days=1)}
    first = repository.append(**args)
    assert repository.current('seller', ('suggestion-1',), now=NOW)['suggestion-1']['hidden']
    assert not repository.current('seller', ('suggestion-1',), now=NOW + timedelta(days=1))['suggestion-1']['hidden']
    assert repository.append(**{**args, 'now': NOW + timedelta(days=2)})['id'] == first['id']
    for delta in (0, 91):
        with pytest.raises(ValueError):
            repository.append(**{**args, 'idempotency_key': f'invalid-{delta}', 'snooze_until': NOW + timedelta(days=delta)})


def test_only_original_actor_can_undo_legacy_dismissal(repository):
    from btx_omni.persistence.actions import SqlActionRepository

    legacy = SqlActionRepository(repository.engine)
    legacy.dismiss_suggestion('suggestion-1', 'seller', NOW)
    assert legacy.dismissed_suggestions('seller') == frozenset({'suggestion-1'})
    assert legacy.dismissed_suggestions('other') == frozenset()
    args = {'user_id': 'other', 'suggestion_id': 'suggestion-1', 'account_id': 'boeing', 'reason': 'UNDO', 'note': '', 'now': NOW,
            'idempotency_key': 'legacy-undo', 'expected_feedback_id': None}
    with pytest.raises(FeedbackConflict):
        repository.append(**args)
    repository.append(**{**args, 'user_id': 'seller'})
    assert not repository.current('seller', ('suggestion-1',), now=NOW)['suggestion-1']['hidden']
    assert legacy.dismissed_suggestions('seller') == frozenset({'suggestion-1'})  # historical row retained


def test_retired_feedback_remains_private_inspectable_and_reversible(repository):
    first = write(repository)
    history = repository.history('seller')
    assert history['total'] == 1 and history['items'][0]['can_undo']
    assert history['items'][0]['identity_state'] == 'RETIRED_UNSTABLE_ID_NOT_REAPPLIED'
    assert repository.history('manager')['items'] == []
    assert repository.receipt('manager', first['id']) is None
    assert repository.receipt('seller', first['id'])['account_id'] == 'boeing'
    repository.append(user_id='seller', suggestion_id='suggestion-1', account_id='boeing', reason='UNDO', note='', now=NOW,
                      idempotency_key='undo-retired', expected_feedback_id=first['id'])
    history = repository.history('seller')
    assert history['total'] == 2 and not any(row['can_undo'] for row in history['items'])
    assert all('idempotency_key' not in row and 'request_hash' not in row for row in history['items'])


@pytest.mark.parametrize('reason', ['WRONG_ACCOUNT', 'ALREADY_DONE'])
def test_user_assertions_require_explanation_and_never_change_work_or_scores(repository, reason):
    args = {'user_id': 'seller', 'suggestion_id': 'suggestion-1', 'account_id': 'boeing', 'reason': reason, 'note': '', 'now': NOW,
            'idempotency_key': 'reported-1', 'expected_feedback_id': None}
    with pytest.raises(ValueError):
        repository.append(**args)
    repository.append(**{**args, 'note': 'Needs review against my local notes'})
    current = repository.current('seller', ('suggestion-1',), now=NOW)['suggestion-1']
    assert current['scope'] == 'CURRENT_USER_ONLY' and current['authority'].startswith('USER_REPORTED_NOT_VERIFIED')


def test_feedback_api_session_csrf_private_visibility_and_closed_body(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from test_hosted_sessions import _production_app, _sign_in

    url = f"sqlite:///{tmp_path / 'api.db'}"
    metadata.create_all(create_engine(url))
    seller = _production_app(monkeypatch, database_url=url)
    assert seller.get('/api/actions').status_code == 401
    session = _sign_in(seller, 'hosted-seller-access')
    headers = {'X-CSRF-Token': session['csrf_token']}
    before = seller.get('/api/actions').json()
    suggestion = before['suggestions'][0]
    path = f"/api/actions/suggestions/{suggestion['id']}/feedback"
    payload = {'reason': 'WRONG_ACCOUNT', 'note': 'Please review the account attribution', 'idempotency_key': 'api-feedback-1', 'expected_revision': suggestion['revision']}
    assert seller.post(path, json=payload).status_code == 403
    assert seller.post(path, headers=headers, json={**payload, 'user_id': 'manager-1'}).status_code == 422
    assert seller.post(path, headers=headers, json={**payload, 'account_id': 'kla'}).status_code == 422
    assert seller.post('/api/actions/suggestions/missing/feedback', headers=headers, json=payload).status_code == 404
    response = seller.post(path, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt['current']['hidden'] and not any(receipt[key] for key in ('external_write', 'canonical_scores_changed', 'work_status_changed'))
    assert seller.get('/api/actions').json()['items'] == before['items']
    assert seller.get('/api/actions').headers['cache-control'] == 'private, no-store'
    manager = TestClient(seller.app, base_url='https://backend.test')
    manager_session = _sign_in(manager, 'hosted-manager-access')
    manager_item = next(item for item in manager.get('/api/actions').json()['suggestions'] if item['id'] == suggestion['id'])
    assert manager_item['feedback'] is None and not manager_item['dismissed']
    undo = {'reason': 'UNDO', 'idempotency_key': 'api-undo-1', 'expected_feedback_id': receipt['current']['id'], 'expected_revision': suggestion['revision']}
    assert manager.post(path, headers={'X-CSRF-Token': manager_session['csrf_token']}, json=undo).status_code == 409
    assert seller.post(path, headers=headers, json=undo).json()['current']['hidden'] is False
    assert seller.post(path, headers=headers, json=payload).json()['current']['reason'] == 'UNDO'
    assert manager.get('/api/actions/suggestion-feedback/history').json()['items'] == []
    assert manager.post(f"/api/actions/suggestion-feedback/{receipt['current']['id']}/undo",
                        headers={'X-CSRF-Token': manager_session['csrf_token']}, json={'idempotency_key': 'foreign-undo'}).status_code == 404
    history = seller.get('/api/actions/suggestion-feedback/history').json()
    assert history['scope'] == 'CURRENT_USER_ONLY' and len(history['items']) == 2
    assert seller.get('/api/actions/suggestion-feedback/history?offset=-1').status_code == 422
