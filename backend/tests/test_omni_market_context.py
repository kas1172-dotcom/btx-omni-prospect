from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from test_market_series import source
from test_omni_commercial_tools import SequentialProvider, imported

from btx_omni.ai.contracts import LanguageResult
from btx_omni.modules.assistant.market_context import selected_market_context
from btx_omni.modules.assistant.service import OmniService
from btx_omni.modules.markets.g17 import parse_g17
from btx_omni.modules.markets.registry import G17_URL, SERIES
from btx_omni.modules.markets.service import MarketService
from btx_omni.persistence.market_series import MarketSeriesRepository
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 9, 8, tzinfo=UTC)


@pytest.fixture
def market(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "market-omni.sqlite"}')
    metadata.create_all(engine)
    repo = MarketSeriesRepository(engine)
    parsed = parse_g17(source(), as_of=NOW.date())
    repo.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    series_id = SERIES[1].id
    filters = {'market': 'Semiconductor', 'market_series_id': series_id,
               'market_vintage_id': repo.snapshot(series_id)['vintage_id'], 'market_metric': 'LEVEL'}
    yield MarketService(repo), filters
    engine.dispose()


def test_selected_market_revalidation_rejects_mismatched_market_revision_and_transformation(tmp_path, market):
    service, filters = market
    sample = imported(tmp_path)
    result = selected_market_context(service, filters, sample)
    assert result['score_effect'] == 'NONE' and result['points'][-1]['value'] == '106.0000'
    assert result['metadata']['geography'] == 'US_NATIONAL_EXCLUDING_TERRITORIES'
    assert any(account['account_id'] == 'kla' for account in result['exposed_accounts'])
    for changed in ({'market': 'Robotics'}, {'market_vintage_id': 'a' * 64}, {'market_metric': 'PWIN'}, {'market_average': '13'}):
        with pytest.raises(ValueError):
            selected_market_context(service, {**filters, **changed}, sample)


def test_omni_uses_canonical_market_read_and_account_history_not_client_numbers(tmp_path, market):
    service, filters = market
    sample = imported(tmp_path)
    original = deepcopy(sample.commercial_ledgers)
    class ConciseProvider(SequentialProvider):
        def synthesize(self, request):
            self.synthesis = request
            # Return seller prose, not an 18KB echo of every tool JSON object.
            return LanguageResult(request.governed_answer.split('\nCanonical public market')[0], self.name, 'fixture', request.evidence_ids)

    provider = ConciseProvider([{'tool': 'read_selected_market', 'arguments': {}}, {'tool': 'read_history', 'arguments': {}}, {'done': True}])
    answer = OmniService(provider).answer(sample, account_id='honeywell', question='Compare this market context with actual account history',
                                          observed_at=NOW, context={'active_filters': {**filters, 'claimed_growth': '99999'}},
                                          intelligence_events=(), work_items=(),
                                          market_reader=lambda scope: selected_market_context(service, scope, sample))
    assert answer.provider_status == 'AVAILABLE', (answer.context_used.get('synthesis_validation'), len(provider.synthesis.governed_answer))
    assert [step['tool'] for step in answer.structured_reads['steps']] == ['read_selected_market', 'read_history']
    assert answer.structured_market['points'][-1]['value'] == '106.0000'
    assert '99999' not in provider.synthesis.governed_answer
    assert sample.commercial_ledgers == original
    assert answer.citation_links[-1].url == G17_URL


def test_provider_cannot_change_market_number_and_failure_keeps_canonical_context(tmp_path, market):
    service, filters = market
    sample = imported(tmp_path)

    class WrongNumber:
        configured = True
        def synthesize(self, request):
            return LanguageResult('Production increased 99999 percent.', 'fixture', 'fixture', ())

    answer = OmniService(WrongNumber()).answer(sample, account_id='honeywell', question='Explain this market', observed_at=NOW,
                                               context={'active_filters': filters}, intelligence_events=(), work_items=(),
                                               market_reader=lambda scope: selected_market_context(service, scope, sample))
    assert answer.provider_status == 'UNAVAILABLE'
    assert answer.context_used['synthesis_validation'] == 'UNSUPPORTED_NUMERIC_CLAIM'
    assert '106.0000' in answer.content and '99999' not in answer.content
    stale = OmniService(None).answer(sample, account_id=None, question='Explain this trend', observed_at=NOW,
                                     context={'active_filters': {**filters, 'market_vintage_id': '0' * 64}}, intelligence_events=(), work_items=(),
                                     market_reader=lambda scope: selected_market_context(service, scope, sample))
    assert stale.context_used['market_context'] == 'STALE_OR_UNAVAILABLE' and stale.recommended_action is None
