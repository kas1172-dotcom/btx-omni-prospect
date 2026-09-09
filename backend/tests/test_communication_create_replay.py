from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from test_communications_settings import NOW, SELLER, service

from btx_omni.modules.communications.service import CommunicationConflictError


def test_create_keys_are_actor_scoped_and_replay_preserves_later_edits(tmp_path):
    communications = service(tmp_path)
    args = {'account_id': 'boeing', 'subject': 'Review evidence', 'body': 'Private local draft', 'recipients': (),
            'principal': SELLER, 'occurred_at': NOW, 'idempotency_key': 'same-client-key'}
    first = communications.create(**args)
    other = replace(SELLER, user_id='different-seller')
    separate = communications.create(**{**args, 'principal': other, 'body': 'Other user draft'})
    assert first.id != separate.id and separate.created_by == other.user_id
    assert {draft.id for draft in communications.list(other)} == {separate.id}
    edited = communications.edit(first.id, principal=SELLER, occurred_at=NOW, body='Later reviewed wording')
    assert communications.create(**args) == edited
    with pytest.raises(CommunicationConflictError, match='different draft content'):
        communications.create(**{**args, 'subject': 'Changed request under the same key'})
    restarted = service(tmp_path)
    assert restarted.create(**args).body == 'Later reviewed wording'
    assert len(restarted.history(first.id, SELLER)) == 2


def test_concurrent_create_retries_record_one_draft_and_one_creation_event(tmp_path):
    communications = service(tmp_path)
    def create(_):
        return communications.create(account_id='boeing', subject='Concurrent draft', body='No sending authorized',
                                     recipients=(), principal=SELLER, occurred_at=NOW, idempotency_key='concurrent-draft')
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(create, range(6)))
    assert len({item.id for item in results}) == 1
    assert len(communications.history(results[0].id, SELLER)) == 1


def test_legacy_raw_key_cannot_return_another_users_private_draft(tmp_path):
    from btx_omni.domain.communications import CommunicationAuditEvent

    communications = service(tmp_path)
    draft = communications.create(account_id='boeing', subject='Private legacy', body='Private', recipients=(),
                                  principal=SELLER, occurred_at=NOW)
    legacy = replace(draft, idempotency_key='legacy-shared-key', version=draft.version + 1)
    communications.repository.save(legacy, CommunicationAuditEvent(None, legacy.id, SELLER.user_id, 'EDITED', NOW, {}), expected_version=draft.version)
    other = replace(SELLER, user_id='other-seller')
    result = communications.create(account_id='boeing', subject='My draft', body='My private text', recipients=(),
                                   principal=other, occurred_at=NOW, idempotency_key='legacy-shared-key')
    assert result.id != legacy.id and result.body == 'My private text' and result.created_by == other.user_id
