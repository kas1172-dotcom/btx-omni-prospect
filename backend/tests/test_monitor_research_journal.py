import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from btx_omni.monitor.research_state import (
    MonitorResearchJournal,
    ResearchLeaseUnavailable,
    runs,
    steps,
)

NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)


@pytest.fixture(params=['sqlite', 'postgresql'])
def journal(tmp_path, request):
    schema = None
    if request.param == 'postgresql':
        url = make_url(os.environ['BTX_DATABASE_URL'])
        assert url.host in {'127.0.0.1', 'localhost'}
        assert url.database == 'btx_omni' or url.database.startswith('btx_omni_e2e')
        base = create_engine(url)
        schema = 'test_research_' + uuid4().hex
        with base.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = base.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "research.db"}')
    runs.create(engine)
    steps.create(engine)
    try:
        yield MonitorResearchJournal(engine)
    finally:
        if schema:
            # Only this test's freshly created, random isolated schema.
            with base.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def acquire(journal, now=NOW, revision='a' * 64):
    return journal.acquire(event_reference='source:public-event', source_revision=revision,
        configuration={'model': 'test', 'policy': '1'}, now=now)


def test_completed_run_replay_reuses_steps_without_provider_call(journal):
    identifier, token = acquire(journal)
    number = journal.start_step(identifier, token, tool='fetch_document', arguments={'source': 'allowed'}, now=NOW)
    journal.complete_step(identifier, token, number, result={'passages': ['actual public text']}, now=NOW)
    journal.finish(identifier, token, result={'outcome': 'RESEARCH_RECORDED'}, now=NOW, complete=True)
    assert acquire(MonitorResearchJournal(journal.engine)) == (identifier, None)
    state = journal.get(identifier)
    assert state['completed_steps'] == 1
    assert state['steps'][0]['result']['passages'] == ['actual public text']
    assert 'lease_token' not in state


def test_completed_run_records_idempotent_deterministic_publication_outcome(journal):
    identifier, token = acquire(journal)
    journal.finish(identifier, token, result={'status': 'RESEARCH_RECORDED', 'published': False}, now=NOW, complete=True)
    outcome = {'published': True, 'state': 'PUBLISHED_SELLER_BRIEF', 'event_id': 'source:public-event',
               'gates': {'canonical_identity_resolved': True}, 'decided_at': NOW.isoformat()}
    journal.record_publication(identifier, outcome=outcome, now=NOW + timedelta(seconds=1))
    journal.record_publication(identifier, outcome=outcome, now=NOW + timedelta(seconds=2))
    state = journal.get(identifier)
    assert state['result']['published'] is True
    assert state['result']['publication_outcome'] == outcome

    paused, paused_token = acquire(journal, revision='b' * 64)
    journal.finish(paused, paused_token, result={'status': 'NO_RETRIEVED_PASSAGES'}, now=NOW, complete=False)
    with pytest.raises(ValueError, match='Only completed'):
        journal.record_publication(paused, outcome=outcome, now=NOW + timedelta(seconds=1))


def test_active_lease_overlap_and_late_expired_completion_are_fenced(journal):
    identifier, old = acquire(journal)
    number = journal.start_step(identifier, old, tool='search_public', arguments={}, now=NOW)
    with pytest.raises(ResearchLeaseUnavailable):
        acquire(journal, NOW + timedelta(seconds=1))
    later = NOW + timedelta(seconds=91)
    same, fresh = acquire(journal, later)
    assert same == identifier and fresh != old
    with pytest.raises(ResearchLeaseUnavailable):
        journal.complete_step(identifier, old, number, result={'late': True}, now=later)
    assert journal.get(identifier)['steps'][0]['status'] == 'INTERRUPTED_UNKNOWN'
    second = journal.start_step(identifier, fresh, tool='search_public', arguments={}, now=later)
    assert second == 2


def test_completed_steps_are_immutable_and_exact_ack_retry_is_idempotent(journal):
    identifier, token = acquire(journal)
    number = journal.start_step(identifier, token, tool='fetch_document', arguments={}, now=NOW)
    journal.complete_step(identifier, token, number, result={'checksum': 'a'}, now=NOW)
    journal.complete_step(identifier, token, number, result={'checksum': 'a'}, now=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match='immutable'):
        journal.complete_step(identifier, token, number, result={'checksum': 'b'}, now=NOW)
    assert journal.get(identifier)['completed_steps'] == 1


def test_retry_and_step_budgets_survive_restart(journal):
    for attempt in range(3):
        now = NOW + timedelta(minutes=2 * attempt)
        identifier, token = acquire(journal, now)
        journal.finish(identifier, token, result={'blocked': 'provider'}, now=now, complete=False)
    with pytest.raises(ResearchLeaseUnavailable, match='budget'):
        acquire(MonitorResearchJournal(journal.engine), NOW + timedelta(minutes=8))
    other, token = acquire(journal, revision='b' * 64)
    number = journal.start_step(other, token, tool='fetch_document', arguments={}, now=NOW, max_steps=1)
    with pytest.raises(ValueError, match='admitted'):
        journal.start_step(other, token, tool='fetch_document', arguments={}, now=NOW)
    with pytest.raises(ValueError, match='unknown outcome'):
        journal.finish(other, token, result={}, now=NOW, complete=True)
    journal.complete_step(other, token, number, result={}, now=NOW)
    with pytest.raises(ValueError, match='budget'):
        journal.start_step(other, token, tool='fetch_document', arguments={}, now=NOW, max_steps=1)


def test_source_revision_and_configuration_do_not_reuse_stale_research(journal):
    original, _ = acquire(journal)
    changed, _ = acquire(journal, revision='b' * 64)
    assert original != changed
    config, _ = journal.acquire(event_reference='source:public-event', source_revision='a' * 64,
        configuration={'model': 'different', 'policy': '1'}, now=NOW)
    assert config not in {original, changed}


def test_invalid_bounds_and_output_size_fail_without_completion(journal):
    with pytest.raises(ValueError):
        journal.acquire(event_reference='event', source_revision='a' * 64, configuration={}, now=NOW, lease_seconds=301)
    identifier, token = acquire(journal)
    number = journal.start_step(identifier, token, tool='fetch_document', arguments={}, now=NOW)
    with pytest.raises(ValueError, match='budget'):
        journal.complete_step(identifier, token, number, result={'text': 'x' * 120000}, now=NOW)
    assert journal.get(identifier)['steps'][0]['status'] == 'STARTED'


def test_invalid_revision_and_naive_finish_do_not_mutate_journal(journal):
    with pytest.raises(ValueError, match='bounds'):
        acquire(journal, revision='z' * 64)
    identifier, token = acquire(journal)
    with pytest.raises(ValueError, match='aware'):
        journal.finish(identifier, token, result={}, now=NOW.replace(tzinfo=None), complete=True)
    assert journal.get(identifier)['status'] == 'RUNNING'


def test_independent_workers_cannot_both_admit_the_same_run(journal):
    def worker():
        try:
            return acquire(MonitorResearchJournal(journal.engine))
        except ResearchLeaseUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    accepted = [result for result in results if result]
    assert len(accepted) == 1
    assert journal.get(accepted[0][0])['attempt_count'] == 1


def test_failed_investigation_cooldown_survives_restart(journal):
    identifier, token = acquire(journal)
    journal.finish(identifier, token, result={'status': 'PROVIDER_FAILED'}, now=NOW, complete=False)
    with pytest.raises(ResearchLeaseUnavailable, match='cooldown'):
        acquire(MonitorResearchJournal(journal.engine), NOW + timedelta(seconds=59))
    assert acquire(journal, NOW + timedelta(seconds=60))[0] == identifier
