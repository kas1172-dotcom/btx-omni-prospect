from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from btx_omni.api.accounts import get_runtime
from btx_omni.api.omni import router
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.models import metadata
from btx_omni.persistence.omni_runs import OmniRunRepository, omni_runs

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def test_private_run_restart_immutable_completion_and_unknown_interrupt(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "runs.db"}')
    omni_runs.create(engine)
    repo = OmniRunRepository(engine)
    identifier = repo.start(actor_id='seller', request={'question': 'private original question'}, now=NOW)
    assert repo.get(identifier, actor_id='manager', now=NOW) is None
    assert repo.get(identifier, actor_id='seller', now=NOW + timedelta(minutes=6))['operational_state'] == 'INTERRUPTED_OUTCOME_UNKNOWN'
    with engine.connect() as connection:
        assert 'private original question' not in str(connection.execute(select(omni_runs)).mappings().one())
    record = {'answer': 'A grounded response', 'execution': {'external_writes': 0}}
    repo.finish(identifier, actor_id='seller', result=record, now=NOW + timedelta(seconds=10))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: repo.finish(identifier, actor_id='seller', result=record, now=NOW + timedelta(seconds=20)), range(4)))
    reopened = OmniRunRepository(engine)
    result = reopened.get(identifier, actor_id='seller', now=NOW + timedelta(days=1))
    assert result['result'] == record and result['status'] == 'ANSWER_RECORDED'
    assert result['completed_at'].replace(tzinfo=UTC) == NOW + timedelta(seconds=10)
    with pytest.raises(ValueError, match='immutable'):
        repo.finish(identifier, actor_id='seller', result={'answer': 'changed'}, now=NOW + timedelta(seconds=30))
    with pytest.raises(KeyError):
        repo.finish(identifier, actor_id='manager', result=record, now=NOW + timedelta(seconds=30))
    engine.dispose()


def test_run_bounds_and_failed_receipt_are_truthful(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "bounded.db"}')
    omni_runs.create(engine)
    repo = OmniRunRepository(engine)
    with pytest.raises(ValueError):
        repo.start(actor_id='seller', request={'question': 'x' * 40001}, now=NOW)
    identifier = repo.start(actor_id='seller', request={}, now=NOW)
    with pytest.raises(ValueError):
        repo.finish(identifier, actor_id='seller', result={'answer': 'x' * 160001}, now=NOW)
    repo.finish(identifier, actor_id='seller', result={'failure_class': 'TimeoutError'}, now=NOW, failed=True)
    assert repo.get(identifier, actor_id='seller', now=NOW)['status'] == 'FAILED'
    engine.dispose()


def test_actual_omni_api_records_answer_privately_and_fails_before_provider_if_audit_missing(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "api.db"}')
    metadata.create_all(engine)
    runtime = PocRuntime(Settings(database_url=str(engine.url), ai_provider='none'))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_runtime] = lambda: runtime
    app.dependency_overrides[principal] = lambda: Principal('seller', 'Seller', PrincipalRole.SALESPERSON)
    client = TestClient(app)
    response = client.post('/omni', json={'account_id': 'boeing', 'question': 'Summarize Boeing commercial context.'})
    assert response.status_code == 200
    identifier = response.json()['run_id']
    receipt = client.get('/omni/runs/' + identifier)
    assert receipt.headers['cache-control'] == 'private, no-store'
    assert receipt.json()['result']['answer'] == response.json()['content']
    assert receipt.json()['result']['execution']['external_writes'] == 0
    assert receipt.json()['result']['provider_status'] == 'NOT_CONFIGURED'
    app.dependency_overrides[principal] = lambda: Principal('manager', 'Manager', PrincipalRole.MANAGER)
    assert client.get('/omni/runs/' + identifier).status_code == 404
    omni_runs.drop(engine)
    called = []
    monkeypatch.setattr('btx_omni.api.omni.get_ai_provider', lambda *_: called.append(True))
    failed = client.post('/omni', json={'question': 'Read the current account.'})
    assert failed.status_code == 503 and not called
    assert 'No model call was started' in failed.json()['detail']
    engine.dispose()
