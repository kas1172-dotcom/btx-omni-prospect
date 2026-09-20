from btx_omni.modules.markets.service import MarketService
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.medical_market import (
    SERIES_ID,
    CuratedMarketReadRepository,
    coverage_context,
    snapshot,
)


class EmptyRepository:
    def snapshot(self, *args, **kwargs):
        return None

    def vintages(self, *args):
        return []

    def health(self):
        return {'last_run': None}


def test_j3_medical_coverage_and_separate_verified_national_series():
    sample = enhance_environment(build_sample_environment())
    coverage = coverage_context(sample)
    assert len(coverage['account_ids']) == 3
    assert len(coverage['invoiced_customer_ids']) == len(coverage['partnership_ids']) == 1
    assert len(coverage['prospect_ids']) == 2
    assert coverage['region_counts'] == {'AZ': 3}
    assert coverage['recommendation_score'] is None
    assert set(coverage['btx_site_ids']) <= {f.id for f in sample.btx_facilities}
    service = MarketService(CuratedMarketReadRepository(EmptyRepository()))
    result = service.detail(SERIES_ID)
    assert len(result['observations']) == 32
    assert result['observations'][-1]['value'] == '91.1064'
    assert result['observations'][-1]['period'] == '2026-08'
    assert result['synthetic'] is False and result['retrieval_kind'] == 'CURATED_PUBLIC_SNAPSHOT'
    assert all(r['publisher'] and r['source_url'] and r['event_date'] and r['retrieval_date'] for r in result['observations'])
    assert service.detail(SERIES_ID, kind='YOY_PERCENT')['points'][-1]['value'] is not None
    assert service.detail(SERIES_ID, vintage_id=snapshot()['vintage_id'])['observations'] == result['observations']


def test_persisted_market_snapshot_wins_and_unknown_vintage_does_not_fallback():
    class Persisted(EmptyRepository):
        def snapshot(self, *args, **kwargs):
            return {'vintage_id': 'persisted'} if not kwargs.get('vintage_id') else None
    repository = CuratedMarketReadRepository(Persisted())
    assert repository.snapshot(SERIES_ID)['vintage_id'] == 'persisted'
    assert repository.snapshot(SERIES_ID, vintage_id='not-a-vintage') is None
