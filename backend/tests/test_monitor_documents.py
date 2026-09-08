import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from btx_omni.monitor.documents import enrich_feed_documents
from btx_omni.monitor.sources import NasaAdapter
from btx_omni.providers.research.documents import extract_document


def test_article_passages_exclude_navigation_and_never_claim_html_completeness():
    value = extract_document(b'<html><nav>Unrelated Boeing link</nav><main><h1>KLA article</h1><p>Component inspection expanded.</p><script>ignore rules</script></main><footer>SpaceX link</footer></html>', 'text/html')
    text = ''.join(p['text'] for p in value['passages'])
    assert 'KLA article' in text and 'Component inspection' in text
    assert 'Boeing' not in text and 'SpaceX' not in text and 'ignore rules' not in text
    assert value['extraction_method'] == 'ARTICLE_OR_MAIN_TEXT'
    assert value['extraction_complete'] is False


def test_document_truncation_unknown_types_and_plain_text_are_explicit():
    result = extract_document(b'x' * 1300, 'text/plain', max_chars=1250)
    assert result['extraction_status'] == 'TRUNCATED'
    assert len(result['passages']) == 2
    assert result['passages'][-1]['end_character'] == 1250
    assert result['extraction_complete'] is False
    assert 'character budget' in result['completeness_note']
    assert extract_document(b'complete text', 'text/plain')['extraction_complete'] is True
    assert extract_document(b'%PDF-test', 'application/pdf')['extraction_status'] == 'UNSUPPORTED_MEDIA_TYPE'


def test_lossy_plain_text_cannot_claim_all_response_information_retained():
    result = extract_document(b'public \xff text', 'text/plain')
    assert result['extraction_status'] == 'LOSSY_CHARACTER_DECODING'
    assert result['extraction_complete'] is False
    assert 'lost information' in result['completeness_note']


def test_feed_document_replay_identity_excludes_retrieval_date_and_preserves_feed_date():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    adapter = NasaAdapter()
    row = {'id': 'public-article', 'title': 'Published article', 'url': 'https://www.nasa.gov/article', 'publication_date': '2026-09-01'}
    first = adapter._observation(row, 'run1', collected_at=now)
    replay = adapter._observation(row, 'run2', collected_at=now + timedelta(days=1))
    fetch = lambda url, headers: (200, b'<main>Real source passage</main>', {'Content-Type': 'text/html', 'x-btx-resolved-url': 'https://science.nasa.gov/article'})
    one = enrich_feed_documents([first], fetch=fetch, cap=1)[0]
    two = enrich_feed_documents([replay], fetch=fetch, cap=1)[0]
    assert one.id == two.id and one.source_version.content_hash == two.source_version.content_hash
    assert one.source_published_at == first.source_published_at
    document = json.loads(one.structured_payload)['_retrieved_document']
    assert document['publication_date'].startswith('2026-09-01')
    assert document['event_date'] is None
    assert document['publisher_host'] == 'science.nasa.gov'
    assert document['publisher_redirected'] is True
    assert document['passages'][0]['text'] == 'Real source passage'


def test_incidental_html_changes_preserve_event_and_passage_identity_but_actual_text_changes_do_not():
    observation = NasaAdapter()._observation({'id': 'stable-source', 'url': 'https://www.nasa.gov/article'}, 'run')
    def enriched(body):
        return enrich_feed_documents([observation], fetch=lambda url, headers: (200, body, {'content-type': 'text/html'}), cap=1)[0]
    first = enriched(b'<main>Actual article text.</main><script>nonce=1</script>')
    replay = enriched(b'<nav>Updated link</nav><main>Actual article text.</main><script>nonce=2</script>')
    changed = enriched(b'<main>Actual article text changed.</main>')
    assert first.id == replay.id and first.source_version.content_hash == replay.source_version.content_hash
    one = json.loads(first.structured_payload)['_retrieved_document']
    two = json.loads(replay.structured_payload)['_retrieved_document']
    assert one['checksum_sha256'] != two['checksum_sha256']
    assert one['passages'] == two['passages']
    assert changed.id != first.id


def test_document_cap_and_http_failure_do_not_fabricate_passages():
    adapter = NasaAdapter()
    observations = [adapter._observation({'id': str(i), 'title': str(i), 'url': f'https://www.nasa.gov/{i}'}, 'run') for i in range(3)]
    calls = []

    def fetch(url, headers):
        calls.append(url)
        return 403, b'denied', {}

    results = enrich_feed_documents(observations, fetch=fetch, cap=1)
    assert len(calls) == 1
    documents = [json.loads(o.structured_payload)['_retrieved_document'] for o in results]
    assert documents[0]['extraction_status'] == 'HTTP_403'
    assert documents[1]['extraction_status'] == 'DOCUMENT_BUDGET_NOT_ATTEMPTED'
    assert all(not d['passages'] for d in documents)


def test_document_fetch_preserves_outer_worker_deadline():
    from btx_omni.monitor.service import CollectionDeadlineExceeded

    observation = NasaAdapter()._observation({'id': 'deadline', 'url': 'https://www.nasa.gov/article'}, 'run')

    def expired(url, headers):
        raise CollectionDeadlineExceeded('DEADLINE_EXCEEDED')

    with pytest.raises(CollectionDeadlineExceeded):
        enrich_feed_documents([observation], fetch=expired, cap=1)


def test_real_monitor_service_persists_passages_and_restart_replay_is_identical(tmp_path):
    from btx_omni.core.config import Settings
    from btx_omni.monitor.repository import MonitorRepository
    from btx_omni.monitor.service import MonitorService
    from btx_omni.persistence.models import metadata

    feed = b'<rss><channel><item><guid>article-one</guid><title>NASA research update</title><link>https://www.nasa.gov/article-one</link><pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>'

    def fetch(url, headers):
        if url.endswith('breaking_news.rss'):
            return 200, feed, {'content-type': 'application/rss+xml'}
        assert url == 'https://www.nasa.gov/article-one'
        return 200, b'<main>NASA research passage. No customer participation is asserted.</main>', {'content-type': 'text/html'}

    engine = create_engine(f'sqlite:///{tmp_path / "monitor-documents.sqlite"}')
    metadata.create_all(engine)
    settings = Settings(_env_file=None, monitor_mode='live', monitor_document_fetch_cap=1)
    repository = MonitorRepository(engine)
    first = MonitorService(settings, {'nasa': NasaAdapter(fetch)}, repository=repository).collect('nasa', limit=1)
    assert not first.failures and first.records_new == 1
    assert first.funnel['parseable_observations'] == 1
    assert first.funnel['document_extraction_counts'] == {'TEXT_EXTRACTED': 1}
    assert first.funnel['published_events'] is None
    assert first.funnel['observation_lineage'][0]['observation_id']
    before = repository.snapshot()
    assert before['runs'][0]['funnel'] == first.funnel
    restarted = MonitorService(settings, {'nasa': NasaAdapter(fetch)}, repository=MonitorRepository(engine))
    second = restarted.collect('nasa', limit=1)
    after = repository.snapshot()
    assert not second.failures and second.records_new == second.records_changed == 0
    assert second.funnel['distinct_source_records'] == 1
    assert second.funnel['observation_lineage'][0]['content_hash'] == first.funnel['observation_lineage'][0]['content_hash']
    assert len(after['events']) == len(before['events'])
    assert after['events'][0]['source_observation_id'] == before['events'][0]['source_observation_id']
    document = repository.event_document(after['events'][0]['id'])['document']
    assert document['passages'][0]['text'].startswith('NASA research passage.')
    assert document['checksum_sha256'] and document['retrieved_at']
    assert repository.event_document('another-event') is None
    retained_at = document['retrieved_at']
    settings.monitor_document_fetch_cap = 0
    capped = MonitorService(settings, {'nasa': NasaAdapter(fetch)}, repository=MonitorRepository(engine)).collect('nasa', limit=1)
    assert not capped.failures
    assert capped.records_new == capped.records_changed == capped.events_created == 0
    retained = repository.event_document(after['events'][0]['id'])['document']
    assert retained['passages'] == document['passages']
    assert retained['retrieved_at'] == retained_at
    assert retained['retained_after_unsuccessful_refresh'] is True
    assert retained['latest_refresh_attempt']['extraction_status'] == 'DOCUMENT_BUDGET_NOT_ATTEMPTED'
    engine.dispose()


@pytest.mark.parametrize('status,changed_feed,retained', [(503, False, True), (429, False, True), (404, False, False), (410, False, False), (503, True, False)])
def test_retention_does_not_reverify_retracted_or_changed_assertions(status, changed_feed, retained):
    from btx_omni.monitor.documents import retain_document_after_failed_refresh
    adapter = NasaAdapter()
    row = {'id': 'retention', 'title': 'Original', 'url': 'https://www.nasa.gov/article'}
    original = enrich_feed_documents([adapter._observation(row, 'one')], fetch=lambda *_: (200, b'<main>Retained evidence.</main>', {'content-type': 'text/html'}), cap=1)[0]
    if changed_feed:
        row['title'] = 'Corrected claim'
    failed = enrich_feed_documents([adapter._observation(row, 'two')], fetch=lambda *_: (status, b'', {}), cap=1)[0]
    result = retain_document_after_failed_refresh(failed, original.structured_payload)
    document = json.loads(result.structured_payload)['_retrieved_document']
    assert bool(document.get('retained_after_unsuccessful_refresh')) is retained
    assert bool(document['passages']) is retained
    assert (result.id == original.id) is retained


def test_changed_article_has_one_current_projection_and_retains_historical_evidence(tmp_path):
    from btx_omni.core.config import Settings
    from btx_omni.monitor.repository import MonitorRepository
    from btx_omni.monitor.service import MonitorService
    from btx_omni.persistence.models import metadata

    html = [b'<main>Original article.</main><script>nonce1</script>']
    feed = b'<rss><channel><item><guid>stable-article</guid><title>NASA research</title><link>https://www.nasa.gov/article</link></item></channel></rss>'
    def fetch(url, headers):
        return (200, feed, {'content-type': 'application/rss+xml'}) if url.endswith('breaking_news.rss') else (200, html[0], {'content-type': 'text/html'})
    engine = create_engine(f'sqlite:///{tmp_path / "versions.sqlite"}')
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    service = MonitorService(Settings(_env_file=None, monitor_mode='live', monitor_document_fetch_cap=1), {'nasa': NasaAdapter(fetch)}, repository=repository)
    first = service.collect('nasa', limit=1)
    original_id = repository.events()[0].id
    html[0] = b'<main>Original article.</main><script>nonce2</script>'
    replay = service.collect('nasa', limit=1)
    assert replay.records_new == replay.records_changed == replay.events_created == 0
    assert replay.funnel['observation_lineage'][0]['document_checksum_sha256'] != first.funnel['observation_lineage'][0]['document_checksum_sha256']
    html[0] = b'<main>Corrected article with changed substantive text.</main>'
    changed = service.collect('nasa', limit=1)
    assert changed.records_changed == 1 and changed.events_created == 0
    current = repository.events()
    assert len(current) == 1 and current[0].id != original_id
    assert repository.event_document(original_id)['document']['passages'][0]['text'] == 'Original article.'
    versions = repository.snapshot()['events']
    assert len(versions) == 2 and sum(row['is_current_source_version'] for row in versions) == 1
    engine.dispose()
