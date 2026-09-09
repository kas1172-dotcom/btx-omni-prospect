from datetime import UTC, datetime

from btx_omni.monitor.briefs import signal_brief
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.normalization import (
    classify_title,
    normalize_structured_observation,
)
from btx_omni.monitor.ontology import EventType
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.sources import NasaAdapter

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)


def event_and_brief(**fields):
    observation = NasaAdapter()._observation({'id': 'dates', 'title': 'KLA Corporation contract award', 'url': 'https://www.nasa.gov/dates', 'publication_date': '2026-09-08T10:00:00+00:00', **fields}, 'run', collected_at=NOW)
    event = normalize_structured_observation(observation, catalog=MonitorCatalog((AccountWatchProfile('kla', 'KLA Corporation'),)), now=NOW).event
    return event, signal_brief(event, observation, freshness_hours=48, now=NOW)


def test_publication_is_not_an_event_occurrence_date():
    event, brief = event_and_brief()
    assert event.event_date is None
    assert event.source_published_at == datetime(2026, 9, 8, 10, tzinfo=UTC)
    assert brief.publication_timestamp == event.source_published_at
    assert brief.event_timing == 'UNKNOWN'
    assert brief.relevant_event_timestamp is None


def test_explicit_future_event_keeps_its_earlier_publication_date():
    event, brief = event_and_brief(event_date='2026-10-01')
    assert event.event_date == datetime(2026, 10, 1, tzinfo=UTC)
    assert brief.publication_timestamp == datetime(2026, 9, 8, 10, tzinfo=UTC)
    assert brief.event_timing == 'UPCOMING'
    assert brief.relevant_event_timestamp == event.event_date
    assert brief.freshness == 'CURRENT'


def test_unclassified_news_does_not_manufacture_a_supply_chain_change():
    assert classify_title('The Otherworldly Geology of Vasquez Rocks') is EventType.UNCLASSIFIED_PUBLIC_UPDATE


def test_future_publication_is_not_a_current_collected_publication():
    event, brief = event_and_brief(publication_date='2026-10-01')
    assert event.seller_relevance_state.value == 'RESOLVED_NEEDS_REVIEW'
    assert brief.freshness == 'FUTURE_PUBLICATION_DATE'
