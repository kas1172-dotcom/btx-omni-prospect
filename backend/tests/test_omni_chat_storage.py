import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.models import metadata
from btx_omni.persistence.omni_conversations import (
    ConversationRepository,
    conversations,
    feedback,
)
from btx_omni.persistence.omni_runs import OmniRunRepository, omni_runs

NOW = datetime(2026, 9, 20, tzinfo=UTC)
SELLER = Principal('seller', 'Test seller', PrincipalRole.SALESPERSON, 'tenant-a')
OTHER = Principal('seller', 'Test seller', PrincipalRole.SALESPERSON, 'tenant-b')


def test_storage_owner_tenant_retention_feedback_and_real_delete(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "conversations.db"}')
    metadata.create_all(engine)
    repo = ConversationRepository(engine, retention_days=1)
    thread = repo.create(SELLER, NOW)
    runs = OmniRunRepository(engine)
    run = runs.start(actor_id='test', request={}, now=NOW)
    repo.append(thread['id'], SELLER, NOW, version=1, turns=[{'role': 'user', 'text': 'Hello'}, {'role': 'assistant', 'text': 'Hi', 'response': {'run_id': run}}])
    assert repo.get(thread['id'], SELLER, NOW)['title'] == 'Hello'
    assert repo.list(OTHER, NOW) == []
    with pytest.raises(KeyError):
        repo.get(thread['id'], OTHER, NOW)
    with pytest.raises(KeyError):
        repo.delete(thread['id'], OTHER, NOW)
    with pytest.raises(ValueError):
        repo.append(thread['id'], SELLER, NOW, version=1, turns=[])
    repo.rename(thread['id'], SELLER, NOW, 'Review')
    assert repo.get(thread['id'], SELLER, NOW)['title'] == 'Review'
    receipt = repo.rate(thread['id'], SELLER, NOW, run, 'down', 'Needs clarity')
    assert receipt['business_data_changed'] is False
    with pytest.raises(ValueError):
        repo.rate(thread['id'], SELLER, NOW, 'different-run', 'up', '')
    repo.delete(thread['id'], SELLER, NOW)
    with engine.connect() as c:
        for table in (conversations, feedback, omni_runs):
            assert c.scalar(select(func.count()).select_from(table)) == 0
    expired = repo.create(SELLER, NOW)
    assert repo.list(SELLER, NOW + timedelta(days=2)) == []
    with pytest.raises(KeyError):
        repo.get(expired['id'], SELLER, NOW + timedelta(days=2))


@pytest.mark.asyncio
async def test_stream_history_resume_actor_boundary_and_feedback(tmp_path, monkeypatch):
    from test_omni_chat_v2 import FakeChat

    settings = Settings(_env_file=None, database_url=f'sqlite:///{tmp_path / "chat.db"}')
    metadata.create_all(create_engine(settings.database_url))
    runtime = PocRuntime(settings)
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: runtime
    app.dependency_overrides[principal] = lambda: SELLER
    monkeypatch.setattr('btx_omni.api.omni.get_ai_provider', lambda _: FakeChat(
        {'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}}, {'answer': 'Boeing is in the sample data.'}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/omni/chat/stream', json={'question': 'Tell me about Boeing'})
        assert response.status_code == 200 and 'text/event-stream' in response.headers['content-type']
        events = [(part.split('\n')[0][7:], json.loads(part.split('\ndata: ')[1])) for part in response.text.strip().split('\n\n')]
        assert [event for event, _ in events] == ['conversation', 'progress', 'delta', 'answer', 'done']
        final = next(data for event, data in events if event == 'answer')
        identifier = final['conversation_id']
        history = await client.get('/api/omni/conversations/' + identifier)
        assert len(history.json()['turns']) == 2
        assert history.json()['turns'][1]['response']['account_id'] == 'boeing'
        rating = await client.post(f'/api/omni/conversations/{identifier}/feedback', json={'run_id': final['response']['run_id'], 'rating': 'up'})
        assert rating.status_code == 200
        app.dependency_overrides[principal] = lambda: OTHER
        assert (await client.get('/api/omni/conversations/' + identifier)).status_code == 404
        assert (await client.delete('/api/omni/conversations/' + identifier)).status_code == 404
        app.dependency_overrides[principal] = lambda: SELLER
        assert (await client.delete('/api/omni/conversations/' + identifier)).json() == {'deleted': True}
        assert (await client.get('/api/omni/conversations/' + identifier)).status_code == 404
