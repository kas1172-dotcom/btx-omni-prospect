from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from test_communications_settings import (
    MANAGER,
    NOW,
    SELLER,
    RecordingDelivery,
    service,
)

from btx_omni.domain.work import ApprovalStatus
from btx_omni.modules.communications.service import CommunicationConflictError
from btx_omni.persistence.communications import CommunicationVersionConflict


def create(communications):
    return communications.create(account_id='boeing', subject='Review', body='Original saved content', recipients=(),
                                 principal=SELLER, occurred_at=NOW)


def test_stale_edit_review_and_preview_cannot_overwrite_current_content(tmp_path):
    communications = service(tmp_path)
    draft = create(communications)
    approved = communications.decide(draft.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW, expected_version=1)
    assert approved.version == 2
    with pytest.raises(CommunicationConflictError):
        communications.edit(draft.id, principal=SELLER, occurred_at=NOW, body='Stale content', expected_version=1)
    edited = communications.edit(draft.id, principal=SELLER, occurred_at=NOW, body='Reviewed local revision', expected_version=2)
    assert edited.version == 3 and edited.approval_status is ApprovalStatus.PENDING
    with pytest.raises(CommunicationConflictError):
        communications.decide(draft.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW, expected_version=2)

    class RacingPreview(RecordingDelivery):
        def preview(self, current):
            communications.edit(current.id, principal=SELLER, occurred_at=NOW, body='New content during preview', expected_version=3)
            return super().preview(current)

    with pytest.raises(CommunicationVersionConflict):
        communications.preview(draft.id, principal=SELLER, occurred_at=NOW, delivery=RacingPreview())
    latest = service(tmp_path).repository.get(draft.id)
    assert latest.body == 'New content during preview' and latest.version == 4
    assert latest.approval_status is ApprovalStatus.PENDING
    assert [event.event for event in communications.history(draft.id, SELLER)] == ['CREATED', 'APPROVED', 'EDITED', 'EDITED']
    communications.preview(draft.id, principal=SELLER, occurred_at=NOW, delivery=RecordingDelivery())
    assert communications.repository.get(draft.id) == latest
    assert communications.history(draft.id, SELLER)[-1].metadata['draft_version'] == 4


def test_concurrent_same_version_edits_have_one_winner_and_one_audit(tmp_path):
    communications = service(tmp_path)
    draft = create(communications)
    get = communications._get
    barrier = Barrier(2)

    def synchronized_get(identifier):
        result = get(identifier)
        barrier.wait(timeout=5)
        return result

    communications._get = synchronized_get

    def edit(body):
        try:
            return communications.edit(draft.id, body=body, principal=SELLER, occurred_at=NOW, expected_version=1)
        except CommunicationVersionConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, ['First contender', 'Second contender']))
    assert len([item for item in results if item]) == 1
    communications._get = get
    winner = next(item for item in results if item)
    assert communications.repository.get(draft.id) == winner and winner.version == 2
    assert len(communications.history(draft.id, SELLER)) == 2


def test_api_requires_reviewed_version_and_rejects_stale_changes(monkeypatch, tmp_path):
    from test_hosted_sessions import _production_app, _sign_in

    communications = service(tmp_path)
    draft = create(communications)
    client = _production_app(monkeypatch, database_url=str(communications.repository.engine.url))
    session = _sign_in(client, 'hosted-seller-access')
    headers = {'X-CSRF-Token': session['csrf_token']}
    path = f'/api/communications/{draft.id}'
    assert client.patch(path, headers=headers, json={'body': 'No version'}).status_code == 422
    changed = client.patch(path, headers=headers, json={'body': 'First save', 'expected_version': 1})
    assert changed.status_code == 200 and changed.json()['version'] == 2
    assert client.patch(path, headers=headers, json={'body': 'Stale save', 'expected_version': 1}).status_code == 409
    assert client.post(path + '/assist', headers=headers, json={'instruction': 'Concise', 'expected_version': 1}).status_code == 409
    assert client.post(path + '/send?confirmed=true&idempotency_key=sample', headers=headers).status_code == 422
    assert communications.repository.get(draft.id).body == 'First save'
