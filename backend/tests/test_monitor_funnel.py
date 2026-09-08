from dataclasses import replace
from types import SimpleNamespace

from btx_omni.monitor.funnel import collection_funnel
from btx_omni.monitor.ontology import ResolutionState, SellerRelevanceState
from btx_omni.monitor.sources import NasaAdapter


def test_funnel_deduplicates_event_ids_and_preserves_overlapping_market_scope():
    observation = NasaAdapter()._observation({'id': 'one', 'url': 'https://www.nasa.gov/one'}, 'run')
    event = SimpleNamespace(id='event-one', resolution_state=ResolutionState.RESOLVED,
                            seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE,
                            markets=('Space', 'Defense'))
    result = collection_funnel([observation, observation], [event, event], complete=True)
    assert result['parseable_observations'] == 2
    assert result['distinct_source_records'] == result['distinct_normalized_events'] == 1
    assert result['resolution_counts'] == {'RESOLVED': 1}
    assert result['by_market']['Space']['seller_eligible'] == 1
    assert result['by_market']['Defense']['seller_eligible'] == 1
    assert result['published_events'] is result['actionable_outcomes'] is result['upstream_retrieved_rows'] is None


def test_failed_partial_collection_and_invalid_payload_are_not_labeled_complete():
    observation = NasaAdapter()._observation({'id': 'one'}, 'run')
    result = collection_funnel([replace(observation, structured_payload='{invalid')], [], complete=False, failures=('DEADLINE_EXCEEDED',))
    assert result['complete'] is False
    assert result['document_extraction_counts'] == {'INVALID_STRUCTURED_PAYLOAD': 1}
    assert result['failures'] == ['DEADLINE_EXCEEDED']
    assert result['distinct_normalized_events'] == 0


def test_durable_empty_failure_list_is_not_a_truthy_json_string_in_health(tmp_path):
    from datetime import UTC, datetime

    from sqlalchemy import create_engine

    from btx_omni.api.monitor import monitor_health
    from btx_omni.api.runtime import PocRuntime
    from btx_omni.core.config import Settings
    from btx_omni.monitor.contracts import CollectionRun, SourceHealth
    from btx_omni.monitor.ontology import SourceHealthState
    from btx_omni.persistence.models import metadata

    settings = Settings(_env_file=None, monitor_mode='live', monitor_durable_state_enabled=True,
                        monitor_schedule_configured=True, database_url=f'sqlite:///{tmp_path / "health.sqlite"}')
    engine = create_engine(settings.database_url)
    metadata.create_all(engine)
    runtime = PocRuntime(settings)
    now = datetime.now(UTC)
    run = CollectionRun('successful', 'nasa', now, now, None)
    runtime.monitor.repository.persist_snapshot(run=run, health=SourceHealth('nasa', SourceHealthState.HEALTHY, now, now), observations=(), events=(), clusters=(), rejected=())
    result = monitor_health(runtime)
    assert result['last_runs'][0]['failures'] == []
    assert result['scheduler_state'] == 'COLLECTION_OBSERVED_CURRENT'
    # This is a health serialization check, not scheduler-triggered execution proof.
    engine.dispose()
