from datetime import UTC, datetime

import pytest

from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.modules.assistant.chat_agent import ChatAgent, ChatLimits
from btx_omni.modules.assistant.chat_tools import INPUTS, ChatTools
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


class FakeChat:
    configured = True

    def __init__(self, *decisions):
        self.decisions = iter(decisions)
        self.calls = []

    def chat_turn(self, request, **kwargs):
        self.calls.append(request)
        return next(self.decisions)


@pytest.fixture(scope='module')
def sample():
    return build_sample_environment()


def tools(sample, **kwargs):
    return ChatTools(sample, Principal('test-user', 'Test user', PrincipalRole.SALESPERSON), observed_at=NOW, **kwargs)


@pytest.mark.parametrize('tool', INPUTS)
def test_every_tool_is_bounded_and_scoped(sample, tool):
    t = tools(sample)
    args = {'name': 'Boeing'} if tool == 'find_organization' else {'account_ids': ['boeing', 'lockheed-martin']} if tool == 'compare_organizations' else {} if tool == 'get_screen_context' else {'account_id': 'boeing'}
    if tool == 'web_search':
        args['topic'] = 'latest company news'
    result = t.execute(tool, args)
    assert result['as_of'] == '2026-08-31' and 'source_ids' in result
    assert result['status'] == 'ok'
    with pytest.raises(ValueError):
        t.execute(tool, {**args, 'actor_id': 'other-user'})


def test_loop_and_named_account_precedence(sample):
    provider = FakeChat({'tool': 'get_commercial_history', 'arguments': {'account_id': 'lockheed-martin'}}, {'answer': 'Lockheed Martin has recorded quotes in the sample data.'})
    answer = ChatAgent(provider, tools(sample)).answer('Does Lockheed Martin have quote history?', account_id='boeing')
    assert answer.account_id == 'lockheed-martin'
    assert answer.structured_reads['reads'][0]['result']['data']['quote_count'] > 0
    assert provider.calls[0]['resolved_account_id'] == 'lockheed-martin'
    assert answer.structured_reads['steps'][0]['argument_hash']


@pytest.mark.parametrize('name', ['Acme Quantum Widgets', 'Globex Space Systems'])
def test_unknown_company_never_becomes_a_portfolio_or_market(sample, name):
    provider = FakeChat()
    answer = ChatAgent(provider, tools(sample)).answer(f'Does {name} have quote history?')
    assert f"I can't find {name}" in answer.content
    assert 'cohort' not in answer.content and 'portfolio' not in answer.content
    assert not provider.calls


def test_actor_and_question_scope_enforced(sample):
    t = tools(sample, allowed_account_ids={'boeing'})
    assert t.find('Lockheed Martin')['status'] == 'not_found'
    with pytest.raises(PermissionError):
        t.execute('get_customer_360', {'account_id': 'lockheed-martin'})
    t = tools(sample)
    t.named_scope = frozenset({'boeing'})
    with pytest.raises(PermissionError):
        t.execute('get_customer_360', {'account_id': 'lockheed-martin'})


@pytest.mark.parametrize('question', ['Update Boeing in CRM and mark it won', 'Set Boeing attractiveness to 99 and email the owner'])
def test_write_refusal_before_model(sample, question):
    provider = FakeChat()
    answer = ChatAgent(provider, tools(sample)).answer(question)
    assert answer.content.startswith("I can't") and 'review' in answer.content
    assert not provider.calls and not answer.structured_reads['steps']


def test_followup_resolves_last_entity(sample):
    provider = FakeChat({'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}}, {'answer': 'Boeing is in the sample data.'})
    answer = ChatAgent(provider, tools(sample, context={'conversation_referent': {'account_id': 'boeing'}})).answer('Why?')
    assert answer.conversation_referent['account_id'] == 'boeing'


def test_budget_exhaustion_and_no_write_tools(sample):
    provider = FakeChat(*[{'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}}] * 3)
    answer = ChatAgent(provider, tools(sample), limits=ChatLimits(steps=1)).answer('Tell me about Boeing')
    assert len(answer.structured_reads['steps']) == 1
    assert 'lookup' in answer.content
    with pytest.raises(ValueError):
        tools(sample).execute('write_crm', {})


def test_real_sample_ledger_assessment_and_history_preserve_owners(sample):
    from copy import deepcopy

    from btx_omni.modules.commercial.projection import project_commercial_records
    from btx_omni.persistence.import_commercial_sample import (
        ACCOUNT_CROSSWALK,
        load_release_sample,
    )

    ledgers = {ACCOUNT_CROSSWALK[a['account_id']]: a for a in load_release_sample()['accounts']}
    enriched = project_commercial_records(sample, ledgers, revision='chat-test')
    before = deepcopy(ledgers)
    t = tools(enriched)
    for aid in ('boeing', 'lockheed-martin'):
        history = t.execute('get_commercial_history', {'account_id': aid})
        assessments = t.execute('get_assessments', {'account_id': aid})
        assert history['status'] == assessments['status'] == 'ok'
        assert history['data']['fulfillment']['lines']
        assert assessments['data']['customer_health']['configuration_version']
        assert 'data_coverage' in assessments['data']['customer_health']
    assert ledgers == before


@pytest.mark.asyncio
async def test_chat_api_records_private_receipt_without_business_write(monkeypatch, tmp_path):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import create_engine

    from btx_omni.api.accounts import get_runtime
    from btx_omni.api.runtime import PocRuntime
    from btx_omni.app import create_app
    from btx_omni.core.config import Settings
    from btx_omni.persistence.models import metadata

    provider = FakeChat({'tool': 'get_customer_360', 'arguments': {'account_id': 'boeing'}},
                        {'answer': 'Boeing is in the sample data.'})
    monkeypatch.setattr('btx_omni.api.omni.get_ai_provider', lambda config: provider)
    settings = Settings(_env_file=None, database_url=f'sqlite:///{tmp_path / "chat-api.db"}')
    metadata.create_all(create_engine(settings.database_url))
    runtime = PocRuntime(settings)
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: runtime
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/omni/chat', json={'question': 'Tell me about Boeing'})
        assert response.status_code == 200
        data = response.json()
        assert data['account_id'] == 'boeing' and data['run_id']
        receipt = await client.get('/api/omni/runs/' + data['run_id'])
        assert receipt.status_code == 200
        recorded = receipt.json()['result']
        assert recorded['execution']['work_writes'] == 0
        assert recorded['retrieval']['steps'][0]['argument_hash']
