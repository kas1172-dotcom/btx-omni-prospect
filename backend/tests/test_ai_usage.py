from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import (
    LanguageProviderError,
    ProviderStatus,
    PublicWebResearchRequest,
)
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.persistence.ai_usage import AiBudgetExceeded, AiUsageRepository
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)


def test_both_sdk_paths_reserve_actual_receipts_and_share_actor_budget(repository):
    class Models:
        calls = 0

        def generate_content(self, **_kwargs):
            self.calls += 1
            return SimpleNamespace(text='Supported public observation.', usage_metadata=SimpleNamespace(total_token_count=12),
                candidates=[SimpleNamespace(finish_reason='STOP', grounding_metadata=SimpleNamespace(grounding_chunks=[
                    SimpleNamespace(web=SimpleNamespace(uri='https://example.test/source', title='Source'))]))])

    client = SimpleNamespace(models=Models())
    config = AiConfig('gemini', 'fixture-key', 'fixture-model', 'developer', None, 'global', 2,
                      usage=repository, actor_id='seller', daily_actor_limit=2, daily_environment_limit=3)
    provider = GeminiProvider(config, client)
    assert provider._generate_text('not logged', {}) == 'Supported public observation.'
    assert provider.research_public_web(PublicWebResearchRequest('Public-only query')).findings
    with pytest.raises(LanguageProviderError) as error:
        GeminiProvider(config, client)._generate_text('must not run', {})
    assert error.value.status is ProviderStatus.QUOTA
    assert client.models.calls == 2
    assert len(provider.usage_log) == 2
    assert len({row['receipt_id'] for row in provider.usage_log}) == 2
    summary = repository.summary(environment_id='btx-omni-prospect', actor_id='seller', now=datetime.now(UTC))
    assert summary['your_measured_total_tokens'] == 24 and summary['your_reserved_calls'] == 2
    assert repository.summary(environment_id='btx-omni-prospect', actor_id='other', now=datetime.now(UTC))['your_reserved_calls'] == 0


def test_missing_ledger_never_builds_client_and_timeout_is_counted(repository):
    config = AiConfig('gemini', 'fixture-key', 'fixture-model', 'developer', None, 'global', 2)
    provider = GeminiProvider(config)
    provider._build_client = lambda: pytest.fail('Missing ledger must fail before SDK construction')
    with pytest.raises(LanguageProviderError) as error:
        provider._generate_text('not sent', {})
    assert error.value.status is ProviderStatus.UNAVAILABLE

    class TimeoutModels:
        def generate_content(self, **_kwargs):
            raise TimeoutError('private SDK diagnostic')

    from dataclasses import replace
    provider = GeminiProvider(replace(config, usage=repository), SimpleNamespace(models=TimeoutModels()))
    with pytest.raises(LanguageProviderError) as error:
        provider._generate_text('not logged', {})
    assert error.value.status is ProviderStatus.TIMEOUT
    from sqlalchemy import select

    from btx_omni.persistence.ai_usage import ai_call_receipts
    with repository.engine.connect() as connection:
        rows = connection.execute(select(ai_call_receipts)).mappings().all()
    assert len(rows) == 1 and rows[0]['status'] == 'TIMEOUT'
    assert 'private SDK diagnostic' not in str(rows) and 'not logged' not in str(rows)


def test_usage_api_is_authenticated_private_and_cannot_select_another_actor(monkeypatch, repository):
    from hashlib import sha256
    from fastapi.testclient import TestClient
    from test_hosted_sessions import _production_app, _sign_in

    receipt = repository.reserve(environment_id='btx-omni-prospect', actor_id='seller-1', purpose='omni',
                                 model='fixture-model', now=datetime.now(UTC))
    repository.complete(receipt, now=datetime.now(UTC), status='RESPONSE_RECEIVED', usage={'total_tokens': 45})
    client = _production_app(monkeypatch, database_url=str(repository.engine.url),
                             user_access_code_hashes={"seller-1": sha256(b"unique-fixture-seller").hexdigest()})
    assert client.get('/api/settings/ai-usage').status_code == 401
    _sign_in(client, 'unique-fixture-seller')
    response = client.get('/api/settings/ai-usage')
    assert response.status_code == 200 and response.headers['cache-control'] == 'private, no-store'
    assert response.json()['your_measured_total_tokens'] == 45
    manager = TestClient(client.app, base_url='https://backend.test')
    _sign_in(manager, 'hosted-manager-access')
    other = manager.get('/api/settings/ai-usage?actor_id=seller-1').json()
    assert other['workspace_reserved_calls'] == 1 and other['your_reserved_calls'] == 0
    assert other['your_measured_total_tokens'] is None and 'seller-1' not in str(other)


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "usage.db"}')
    metadata.create_all(engine)
    yield AiUsageRepository(engine)
    engine.dispose()


def reserve(repository, **kwargs):
    return repository.reserve(**{'environment_id': 'test:SAMPLE', 'actor_id': 'seller', 'purpose': 'omni', 'model': 'test-model', 'now': NOW, **kwargs})


def test_daily_actor_workspace_caps_and_concurrent_leases_are_durable(repository):
    first = reserve(repository, daily_actor_limit=1, daily_environment_limit=2)
    with pytest.raises(AiBudgetExceeded, match='daily'):
        reserve(repository, daily_actor_limit=1, daily_environment_limit=2)
    repository.complete(first, now=NOW + timedelta(seconds=1), status='TIMEOUT')
    # Failed/unknown calls still consume their reserved daily budget.
    with pytest.raises(AiBudgetExceeded, match='daily'):
        reserve(repository, daily_actor_limit=1, daily_environment_limit=2)
    second = reserve(repository, actor_id='another', daily_actor_limit=1, daily_environment_limit=2)
    with pytest.raises(AiBudgetExceeded, match='Workspace daily'):
        reserve(repository, actor_id='third', daily_actor_limit=1, daily_environment_limit=2)
    repository.complete(second, now=NOW + timedelta(seconds=2), status='RESPONSE_RECEIVED', usage={'total_tokens': 123})
    fresh = AiUsageRepository(create_engine(repository.engine.url))
    try:
        summary = fresh.summary(environment_id='test:SAMPLE', actor_id='seller', now=NOW)
        assert summary['workspace_reserved_calls'] == 2 and summary['your_reserved_calls'] == 1
        assert summary['your_measured_total_tokens'] is None and summary['cost_usd'] is None
        assert summary['your_unknown_usage_calls'] == 1 and 'another' not in str(summary)
        assert reserve(fresh, now=NOW + timedelta(days=1), daily_actor_limit=1, daily_environment_limit=2)
    finally:
        fresh.engine.dispose()


def test_concurrency_rejects_before_call_and_expiry_does_not_refund_daily_calls(repository):
    first = reserve(repository, concurrent_environment_limit=1)
    with pytest.raises(AiBudgetExceeded, match='concurrency'):
        reserve(repository, actor_id='another', concurrent_environment_limit=1)
    later = NOW + timedelta(seconds=181)
    reserve(repository, actor_id='another', now=later, concurrent_environment_limit=1)
    repository.complete(first, now=later, status='RESPONSE_RECEIVED', usage={'total_tokens': 50, 'finish_reason': 'STOP'})
    summary = repository.summary(environment_id='test:SAMPLE', actor_id='seller', now=later)
    assert summary['workspace_reserved_calls'] == 2 and summary['your_measured_total_tokens'] == 50
    with pytest.raises(ValueError, match='rewritten'):
        repository.complete(first, now=later, status='FAILED')


def test_parallel_reservations_cannot_exceed_one_actor_lease(repository):
    def attempt(_):
        try:
            return reserve(repository)
        except AiBudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts = list(executor.map(attempt, range(8)))
    assert sum(item is not None for item in receipts) == 1
    assert repository.summary(environment_id='test:SAMPLE', actor_id='seller', now=NOW)['your_reserved_calls'] == 1


def test_usage_retains_unknowns_and_rejects_prompt_or_private_reasoning_fields(repository):
    receipt = reserve(repository)
    with pytest.raises(ValueError, match='Only bounded usage'):
        repository.complete(receipt, now=NOW, status='RESPONSE_RECEIVED', usage={'prompt': 'Never store private business text'})
    repository.complete(receipt, now=NOW, status='RESPONSE_RECEIVED', usage={'total_tokens': -1, 'elapsed_ms': float('nan')})
    assert repository.summary(environment_id='test:SAMPLE', actor_id='seller', now=NOW)['your_measured_total_tokens'] is None
    with pytest.raises(ValueError, match='bounded POC'):
        reserve(repository, daily_actor_limit=20, daily_environment_limit=10)
    with pytest.raises(ValueError, match='clock'):
        reserve(repository, now=NOW.replace(tzinfo=None))
