from datetime import UTC, datetime
from time import monotonic
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from btx_omni.ai.contracts import PublicWebFinding, PublicWebResearchResult
from btx_omni.monitor.research import MonitorResearchCoordinator
from btx_omni.monitor.research_state import MonitorResearchJournal, runs, steps
from btx_omni.providers.research.http import PublicResponse

NOW = datetime(2026, 9, 8, 19, tzinfo=UTC)
RECORD = {'event_id': 'event-1', 'source_id': 'publisher', 'source_url': 'https://example.com/public',
          'title': 'Public manufacturing expansion', 'document': None, 'internal_secret': 'MUST_NOT_LEAVE'}


class Provider:
    name = 'test-only-provider'
    configured = True
    config = SimpleNamespace(model='isolated-test-model', timeout_seconds=1)

    def __init__(self, choices):
        self.choices, self.reads, self.searches = iter(choices), [], []

    def choose_canonical_read(self, request):
        self.reads.append(request)
        return next(self.choices)

    def research_public_web(self, request):
        self.searches.append(request)
        return PublicWebResearchResult((PublicWebFinding('search-1', 'Public product detail',
            'https://example.com/product', 'Example publisher', 'Discovery summary, not article text'),), self.name, self.config.model)


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "coordinator.db"}')
    runs.create(engine)
    steps.create(engine)
    yield SimpleNamespace(research=MonitorResearchJournal(engine))
    engine.dispose()


def fetch(url, **kwargs):
    assert url.startswith('https://example.com/')
    assert kwargs['max_bytes'] == 2_000_000
    return PublicResponse(200, b'<article>Manufacturing facility expansion with precision housings.</article>',
        {'content-type': 'text/html'}, url, 0)


def run(repository, provider, **kwargs):
    return MonitorResearchCoordinator(repository, provider, fetch=fetch, clock=lambda: NOW).investigate(
        RECORD, source_revision='a' * 64, deadline_monotonic=monotonic() + 30, **kwargs)


def test_model_selects_real_bounded_public_steps_and_restart_replays_without_calls(repository):
    provider = Provider([{'tool': 'fetch_document', 'arguments': {'source_id': 'primary'}},
                         {'tool': 'search_public', 'arguments': {'focus': 'components'}}, {'done': True}])
    result = run(repository, provider)
    assert result['status'] == 'RESEARCH_RECORDED'
    assert result['published'] is False
    assert result['tools_used'] == 2
    assert result['documents'][0]['document']['passages'][0]['text'].startswith('Manufacturing facility')
    assert result['documents'][0]['document']['extraction_complete'] is False
    state = repository.research.get(result['run_id'])
    assert len(state['steps']) == 5
    replay = run(repository, Provider([]))
    assert replay['reused'] and replay['run_id'] == result['run_id']
    assert 'MUST_NOT_LEAVE' not in repr(provider.reads) + repr(provider.searches)
    assert provider.searches[0].governed_context == ()


@pytest.mark.parametrize('choice', [
    {'tool': 'write_crm', 'arguments': {}},
    {'tool': 'fetch_document', 'arguments': {'source_id': 'http://127.0.0.1/secrets'}},
    {'tool': 'search_public', 'arguments': {'focus': 'private customer orders'}},
    {'tool': 'search_public', 'arguments': {'focus': 'program', 'query': 'private'}},
])
def test_unapproved_tool_scope_never_executes(repository, choice):
    provider = Provider([choice])
    result = run(repository, provider)
    assert result['status'] == 'PROVIDER_OR_SELECTION_FAILED'
    assert not result['documents'] and not provider.searches
    assert repository.research.get(result['run_id'])['steps'][0]['status'] == 'FAILED'


def test_provider_done_without_passages_is_not_success_or_publication(repository):
    result = run(repository, Provider([{'done': True}]))
    assert result['status'] == 'NO_RETRIEVED_PASSAGES'
    assert repository.research.get(result['run_id'])['status'] == 'PAUSED'


def test_step_cap_returns_partial_not_complete_and_repeated_fetch_is_rejected(repository):
    result = run(repository, Provider([{'tool': 'fetch_document', 'arguments': {'source_id': 'primary'}}]), max_tools=1)
    assert result['status'] == 'TOOL_BUDGET_EXHAUSTED'
    assert repository.research.get(result['run_id'])['status'] == 'PAUSED'
    assert result['published'] is False


def test_provider_unavailable_is_reported_without_starting_a_journal_or_call(repository):
    provider = Provider([])
    provider.configured = False
    assert run(repository, provider)['status'] == 'NOT_CONFIGURED'
