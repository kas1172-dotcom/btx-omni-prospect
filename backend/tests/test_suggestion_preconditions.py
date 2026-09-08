from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from test_hosted_sessions import _production_app, _sign_in

from btx_omni.persistence.models import metadata
from btx_omni.persistence.work_feedback import (
    FeedbackConflict,
    SuggestionFeedbackRepository,
)


def test_changed_source_blocks_new_feedback_but_does_not_erase_committed_receipt(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "feedback.db"}')
    metadata.create_all(engine)
    repo = SuggestionFeedbackRepository(engine)
    args = {'user_id': 'seller', 'suggestion_id': 'suggestion-v2-test', 'account_id': 'kla', 'reason': 'NOT_RELEVANT',
            'note': 'Personal relevance only', 'now': datetime.now(UTC), 'idempotency_key': 'lost-ack-1',
            'expected_feedback_id': None, 'source_revision': 'a' * 64, 'current_source_revision': 'a' * 64}
    first = repo.append(**args)
    assert repo.append(**{**args, 'current_source_revision': 'b' * 64})['id'] == first['id']
    with pytest.raises(FeedbackConflict, match='evidence changed'):
        repo.append(**{**args, 'idempotency_key': 'new-request-2', 'current_source_revision': 'b' * 64})
    with pytest.raises(FeedbackConflict, match='different feedback'):
        repo.append(**{**args, 'source_revision': 'b' * 64, 'current_source_revision': 'b' * 64})
    assert repo.history('seller')['total'] == 1
    assert repo.current('seller', ('suggestion-v2-test',), now=args['now'], source_revisions={'suggestion-v2-test': 'a' * 64})['suggestion-v2-test']['hidden']
    changed = repo.current('seller', ('suggestion-v2-test',), now=args['now'], source_revisions={'suggestion-v2-test': 'b' * 64})['suggestion-v2-test']
    assert not changed['hidden'] and changed['source_changed'] and changed['source_revision'] == 'a' * 64
    engine.dispose()


def test_api_requires_reviewed_source_before_conversion_and_feedback(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path / "api.db"}'
    metadata.create_all(create_engine(url))
    client = _production_app(monkeypatch, database_url=url)
    session = _sign_in(client, 'hosted-seller-access')
    headers = {'X-CSRF-Token': session['csrf_token']}
    before = client.get('/api/actions').json()
    suggestion = next(item for item in before['suggestions'] if not item['converted_action_id'] and not item['conversion_blocked'])
    root = f"/api/actions/suggestions/{suggestion['id']}"
    assert client.post(root + '/convert', headers=headers, json={}).status_code == 422
    assert client.post(root + '/convert', headers=headers, json={'expected_revision': '0' * 64}).status_code == 409
    feedback = {'reason': 'NOT_RELEVANT', 'idempotency_key': 'stale-review-1', 'expected_revision': '0' * 64}
    assert client.post(root + '/feedback', headers=headers, json=feedback).status_code == 409
    assert client.get('/api/actions').json()['items'] == before['items']
    assert client.get('/api/actions/suggestion-feedback/history').json()['total'] == 0
    created = client.post(root + '/convert', headers=headers, json={'expected_revision': suggestion['revision']})
    assert created.status_code == 200, created.text
    # A retry returns the already-authorized work, never a second Action or a stale edit.
    replay = client.post(root + '/convert', headers=headers, json={'expected_revision': '0' * 64})
    assert replay.json()['id'] == created.json()['id']
    assert len(client.get('/api/actions').json()['items']) == len(before['items']) + 1
