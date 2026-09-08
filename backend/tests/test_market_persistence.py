from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from test_market_series import source

from btx_omni.modules.markets.g17 import parse_g17
from btx_omni.modules.markets.registry import G17_URL, SERIES
from btx_omni.modules.markets.service import MarketService
from btx_omni.persistence.market_series import MarketSeriesRepository
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 9, 8, 11, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "market.sqlite"}')
    metadata.create_all(engine)
    yield MarketSeriesRepository(engine)
    engine.dispose()


def test_vintage_replay_revision_restart_and_historical_reads(repository):
    parsed = parse_g17(source(), as_of=date(2026, 9, 8))
    first = repository.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    assert first['created_vintages'] == 4 and first['replayed_series'] == 0
    series_id = SERIES[0].id
    original = repository.snapshot(series_id)
    replay = repository.store(parsed, retrieved_at=NOW + timedelta(seconds=1), source_url=G17_URL)
    assert replay['created_vintages'] == 0 and replay['replayed_series'] == 4
    changed = deepcopy(parsed)
    changed['series'][0]['observations'][0]['value'] = '99'
    updated = repository.store(changed, retrieved_at=NOW + timedelta(seconds=2), source_url=G17_URL)
    assert updated['created_vintages'] == 1 and updated['replayed_series'] == 3
    reopened = MarketSeriesRepository(create_engine(repository.engine.url))
    try:
        assert reopened.snapshot(series_id)['observations'][0]['value'] == '99'
        historical = reopened.snapshot(series_id, vintage_id=original['vintage_id'])
        assert historical['observations'][0]['value'] == '100' and not historical['is_current']
        assert historical['last_verified_at'] is None
        assert reopened.snapshot(SERIES[1].id, vintage_id=original['vintage_id']) is None
        assert len(reopened.vintages(series_id)) == 2
    finally:
        reopened.engine.dispose()
    with pytest.raises(ValueError, match='Stale'):
        repository.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    assert repository.snapshot(series_id)['observations'][0]['value'] == '99'


def test_source_copies_and_line_shifts_do_not_manufacture_new_vintages(repository):
    parsed = parse_g17(source(), as_of=NOW.date())
    repository.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    changed = deepcopy(parsed)
    changed['source_sha256'] = 'a' * 64
    for item in changed['series']:
        for row in item['observations']:
            row['source_line'] += 42
    report = repository.store(changed, retrieved_at=NOW + timedelta(seconds=1), source_url=G17_URL)
    assert report['created_vintages'] == 0 and report['replayed_series'] == 4
    assert repository.health()['last_run']['source_sha256'] == 'a' * 64


def test_failed_refresh_retains_data_and_reports_failure_not_fresh_verification(repository):
    service = MarketService(repository)
    response = SimpleNamespace(status=200, headers={'content-type': 'text/plain'}, body=source(), final_url=G17_URL)
    assert service.refresh(fetch=lambda *args, **kwargs: response, now=lambda: NOW)['status'] == 'SUCCEEDED'
    original = repository.snapshot(SERIES[0].id)
    response.status = 503
    failed = service.refresh(fetch=lambda *args, **kwargs: response, now=lambda: NOW + timedelta(minutes=1))
    assert failed['status'] == 'FAILED' and failed['prior_data_retained']
    assert repository.snapshot(SERIES[0].id) == original
    assert service.detail(SERIES[0].id)['source_health']['last_run']['status'] == 'FAILED'
    response.status, response.body = 200, b'broken'
    assert service.refresh(fetch=lambda *args, **kwargs: response, now=lambda: NOW + timedelta(minutes=2))['reason'] == 'SOURCE_CONTRACT_CHANGED'
    assert service.overview()['score_effect'] == 'NONE'


def test_partial_or_changed_metadata_rejects_entire_refresh(repository):
    parsed = parse_g17(source(), as_of=NOW.date())
    parsed['series'][0]['metadata']['geography'] = 'Arizona'
    with pytest.raises(ValueError, match='metadata'):
        repository.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    assert repository.snapshot(SERIES[0].id) is None


def test_all_missing_series_remains_unknown_without_crashing_scorecard(repository):
    parsed = parse_g17(source(values=[None] * 7), as_of=NOW.date())
    repository.store(parsed, retrieved_at=NOW, source_url=G17_URL)
    assert all(item['latest'] is None and item['points'] == [] for item in MarketService(repository).overview()['series'])


def test_market_api_authorizes_validates_and_reads_saved_vintage(repository):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from btx_omni.api.accounts import get_runtime
    from btx_omni.api.markets import router
    from btx_omni.api.runtime import PocRuntime
    from btx_omni.core.config import Settings

    runtime = PocRuntime(Settings(environment='production', database_url=str(repository.engine.url)))
    runtime.markets = MarketService(repository)
    repository.store(parse_g17(source(), as_of=NOW.date()), retrieved_at=NOW, source_url=G17_URL)
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_runtime] = lambda: runtime
    with TestClient(app) as client:
        assert client.get('/api/markets').status_code == 401
        runtime.settings.environment = 'development'
        result = client.get('/api/markets?kind=YOY_PERCENT')
        assert result.status_code == 200 and result.json()['transformation'] == 'YOY_PERCENT'
        assert result.json()['score_effect'] == 'NONE'
        assert client.get('/api/markets?kind=CAPACITY').status_code == 422
        assert client.get('/api/markets/not-a-series').status_code == 404
        assert client.get(f'/api/markets/{SERIES[0].id}?vintage_id=unsafe').status_code == 422
        detail = client.get(f'/api/markets/{SERIES[0].id}').json()
        assert detail['source_sha256'] and detail['release_date'] is None


def test_worker_refresh_daily_replay_hourly_failure_retry_and_budget(repository):
    from time import monotonic
    service = MarketService(repository, worker_enabled=True)
    response = SimpleNamespace(status=200, headers={'content-type': 'text/plain'}, body=source(), final_url=G17_URL)
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        return response

    assert service.worker_refresh(deadline_monotonic=monotonic() + 10, now=lambda: NOW, fetch=fetch)['status'] == 'SKIPPED_DEADLINE'
    assert not calls
    first = service.worker_refresh(deadline_monotonic=monotonic() + 25, now=lambda: NOW, fetch=fetch)
    assert first['status'] == 'SUCCEEDED'
    assert service.worker_refresh(deadline_monotonic=monotonic() + 25, now=lambda: NOW + timedelta(hours=23), fetch=fetch)['status'] == 'NOT_DUE'
    assert len(calls) == 1
    response.status = 503
    assert service.worker_refresh(deadline_monotonic=monotonic() + 25, now=lambda: NOW + timedelta(hours=24), fetch=fetch)['status'] == 'FAILED'
    assert service.worker_refresh(deadline_monotonic=monotonic() + 25, now=lambda: NOW + timedelta(hours=24, minutes=59), fetch=fetch)['status'] == 'NOT_DUE'
    response.status = 200
    replay = service.worker_refresh(deadline_monotonic=monotonic() + 25, now=lambda: NOW + timedelta(hours=25), fetch=fetch)
    assert replay['replayed_series'] == 4 and replay['created_vintages'] == 0 and len(calls) == 3
    assert service.health()['schedule_status'] == 'WORKER_ENABLED_SCHEDULER_UNVERIFIED'


def test_public_read_deadline_does_not_publish_a_late_source_result(repository):
    from time import monotonic, sleep
    service = MarketService(repository)

    def fetch(*args, **kwargs):
        sleep(.1)
        return SimpleNamespace(status=200, headers={'content-type': 'text/plain'}, body=source(), final_url=G17_URL)

    report = service.refresh(fetch=fetch, now=lambda: NOW, deadline_monotonic=monotonic() + .02)
    assert report['status'] == 'FAILED' and report['reason'] == 'REFRESH_DEADLINE'
    assert repository.snapshot(SERIES[0].id) is None
