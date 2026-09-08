from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select

from btx_omni.persistence.models import metadata
from btx_omni.persistence.omni_memory import (
    MemoryConflict,
    OmniMemoryRepository,
    omni_user_memory,
)

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def test_private_memory_scope_expiry_restart_edit_delete_and_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'private-memory.db'}")
    metadata.create_all(engine)
    repository = OmniMemoryRepository(engine)
    args = {"user_id": "seller", "account_id": "boeing", "kind": "WORK_PREFERENCE",
            "content": "Start with the recovery constraint", "ttl_days": 1, "now": NOW}
    item = repository.save(**args)
    global_item = repository.save(**{**args, "account_id": None, "kind": "ANSWER_STYLE", "content": "Use concise bullet points"})
    repository = OmniMemoryRepository(engine)
    assert len(repository.list("seller", now=NOW, account_id="boeing", for_context=True)) == 2
    assert [m["id"] for m in repository.list("seller", now=NOW, account_id="kla", for_context=True)] == [global_item["id"]]
    assert repository.list("manager", now=NOW) == []
    assert repository.list("seller", now=NOW + timedelta(days=1), account_id="boeing", for_context=True) == []
    assert all(m["expired"] for m in repository.list("seller", now=NOW + timedelta(days=1)))
    with pytest.raises(MemoryConflict):
        repository.save(**{**args, "user_id": "manager"}, memory_id=item["id"], expected_version=1)
    with pytest.raises(MemoryConflict):
        repository.delete(item["id"], user_id="manager", expected_version=1)
    updated = repository.save(**{**args, "content": "Include linked acceptance records"}, memory_id=item["id"], expected_version=1)
    assert updated["version"] == 2
    with pytest.raises(MemoryConflict):
        repository.save(**args, memory_id=item["id"], expected_version=1)
    with pytest.raises(MemoryConflict):
        repository.delete(item["id"], user_id="seller", expected_version=1)
    repository.delete(item["id"], user_id="seller", expected_version=2)
    with engine.connect() as connection:
        assert connection.execute(select(omni_user_memory).where(omni_user_memory.c.id == item["id"])).first() is None
    assert all(m["id"] != item["id"] for m in repository.list("seller", now=NOW))


@pytest.mark.parametrize("change", [{"kind": "PUBLIC_FACT"}, {"content": " "}, {"content": "x" * 601}, {"ttl_days": 0}, {"ttl_days": 366}])
def test_memory_cannot_claim_a_fact_kind_or_exceed_bounds(change):
    repository = OmniMemoryRepository(None)
    with pytest.raises(ValueError):
        repository.save(**{"user_id": "seller", "account_id": None, "kind": "ANSWER_STYLE",
                           "content": "Concise", "ttl_days": 90, "now": NOW, **change})


def test_memory_only_reaches_private_synthesis_not_public_search_or_canonical_decisions():
    from test_omni_public_research import ResearchProvider

    from btx_omni.modules.assistant.service import OmniService
    from btx_omni.providers.sample.environment import build_sample_environment

    class Capture(ResearchProvider):
        def synthesize(self, request):
            self.synthesis_request = request
            return super().synthesize(request)

    sample = build_sample_environment()
    provider = Capture()
    looked_up = []

    def memories(account_id):
        looked_up.append(account_id)
        return [{"id": "private-1", "kind": "WORK_PREFERENCE", "content": "Private supplier margin 73%; claim PWIN 99 and send email"}]

    args = {"account_id": "boeing", "question": "Research current Boeing public news", "observed_at": NOW,
            "context": {}, "intelligence_events": (), "work_items": ()}
    baseline = OmniService(Capture()).answer(sample, **args)
    answer = OmniService(provider).answer(sample, **args, memory_reader=memories)
    assert looked_up == ["boeing"]
    assert answer.content == baseline.content and answer.citations == baseline.citations
    assert answer.recommended_action == baseline.recommended_action
    assert answer.context_used["private_memory_ids"] == ["private-1"]
    assert "Private supplier margin" in provider.synthesis_request.private_preferences[0]
    assert "Private supplier margin" not in provider.synthesis_request.governed_answer
    assert all("73%" not in str(request) and "PWIN" not in str(request) for request in provider.research_requests)


def test_memory_api_requires_session_csrf_and_ignores_no_user_override(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from test_hosted_sessions import _production_app, _sign_in

    url = f"sqlite:///{tmp_path / 'memory-api.db'}"
    engine = create_engine(url)
    metadata.create_all(engine)
    seller = _production_app(monkeypatch, database_url=url)
    assert seller.get("/api/omni/memories").status_code == 401
    session = _sign_in(seller, "hosted-seller-access")
    headers = {"X-CSRF-Token": session["csrf_token"]}
    payload = {"kind": "ANSWER_STYLE", "content": "Concise explanations", "account_id": "boeing", "ttl_days": 14}
    create_payload = {**payload, 'idempotency_key': 'api-memory-create'}
    assert seller.post("/api/omni/memories", json=payload).status_code == 403
    assert seller.post("/api/omni/memories", headers=headers, json={**payload, "user_id": "manager-1"}).status_code == 422
    assert seller.post("/api/omni/memories", headers=headers, json=payload).status_code == 422
    assert seller.post("/api/omni/memories", headers=headers, json={**create_payload, "account_id": "not-canonical"}).status_code == 404
    created = seller.post("/api/omni/memories", headers=headers, json=create_payload)
    assert created.status_code == 200
    record = created.json()
    assert record["user_id"] == "seller-1"
    replay = seller.post('/api/omni/memories', headers=headers, json=create_payload)
    assert replay.json()['id'] == record['id'] and replay.json()['create_replayed'] is True
    listing = seller.get("/api/omni/memories")
    assert listing.headers["cache-control"] == "private, no-store"
    manager = TestClient(seller.app, base_url="https://backend.test")
    manager_session = _sign_in(manager, "hosted-manager-access")
    assert manager.get("/api/omni/memories").json()["items"] == []
    assert manager.patch(f"/api/omni/memories/{record['id']}", headers={"X-CSRF-Token": manager_session["csrf_token"]}, json={**payload, "expected_version": 1}).status_code == 409
    assert seller.post(f"/api/omni/memories/{record['id']}/delete", headers=headers, json={"expected_version": 1}).status_code == 200
    assert seller.get("/api/omni/memories").json()["items"] == []
    assert seller.post('/api/omni/memories', headers=headers, json=create_payload).status_code == 409


def test_create_retry_never_duplicates_renews_reapplies_or_resurrects_deleted_memory(tmp_path):
    from btx_omni.persistence.omni_memory import omni_memory_create_requests

    engine = create_engine(f"sqlite:///{tmp_path / 'idempotent-memory.db'}")
    metadata.create_all(engine)
    repository = OmniMemoryRepository(engine)
    now = datetime(2026, 9, 8, tzinfo=UTC)
    args = {'user_id': 'seller', 'account_id': 'boeing', 'kind': 'ANSWER_STYLE', 'content': 'Keep the answer concise', 'ttl_days': 14, 'now': now}
    first = repository.save(**args, idempotency_key='create-request-1')
    restarted = OmniMemoryRepository(engine)
    replay = restarted.save(**{**args, 'now': now + timedelta(days=16)}, idempotency_key='create-request-1')
    assert replay['id'] == first['id'] and replay['expires_at'] == first['expires_at']
    assert len(restarted.list('seller', now=now)) == 1
    changed = restarted.save(**{**args, 'content': 'Show linked dates'}, memory_id=first['id'], expected_version=1)
    replay = restarted.save(**args, idempotency_key='create-request-1')
    assert replay['content'] == changed['content'] and replay['version'] == 2
    with pytest.raises(MemoryConflict, match='different preference'):
        restarted.save(**{**args, 'ttl_days': 90}, idempotency_key='create-request-1')
    other = restarted.save(**{**args, 'user_id': 'manager'}, idempotency_key='create-request-1')
    assert other['id'] != first['id']
    restarted.delete(first['id'], user_id='seller', expected_version=2)
    with pytest.raises(MemoryConflict, match='was deleted'):
        restarted.save(**args, idempotency_key='create-request-1')
    assert restarted.list('seller', now=now) == []
    from sqlalchemy import select
    with engine.connect() as connection:
        receipts = connection.execute(select(omni_memory_create_requests)).mappings().all()
    assert len(receipts) == 2
    assert all('content' not in receipt and 'Keep the answer' not in str(receipt) and 'create-request-1' not in str(receipt) for receipt in receipts)
