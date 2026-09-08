from dataclasses import replace
from datetime import UTC, datetime, timedelta

from btx_omni.modules.scoring.public_inputs import public_signal_assessment
from btx_omni.monitor.briefs import signal_brief
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.sources import NasaAdapter

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)


def records(**changes):
    observation = NasaAdapter()._observation({'id': 'confidence',
        'title': 'KLA Corporation contract award', 'url': 'https://www.nasa.gov/confidence',
        'publication_date': '2026-09-08T10:00:00+00:00', 'event_date': '2026-09-07', **changes},
        'run', collected_at=NOW)
    event = normalize_structured_observation(observation,
        catalog=MonitorCatalog((AccountWatchProfile('kla', 'KLA Corporation'),)), now=NOW).event
    return event, observation


def score(event, observation, now=NOW):
    return public_signal_assessment(event, observation, now=now, freshness_hours=48)


def test_actual_monitor_brief_uses_the_canonical_family_and_source_factors():
    event, observation = records()
    decision = score(event, observation)
    assert signal_brief(event, observation, freshness_hours=48, now=NOW).signal_confidence == decision
    assert decision['family'] == 'signal_confidence'
    assert decision['subject_id'] == event.id
    assert decision['score'] is not None
    assert decision['data_coverage']['present'] == 7
    assert decision['data_coverage']['applicable'] == 8
    factors = {f['key']: f for f in decision['factors']}
    assert factors['independent_corroboration']['points'] is None
    assert factors['source_reliability']['points'] == 90
    assert all(f['truth_class'] == 'PUBLIC_SOURCE' for f in decision['factors'])


def test_repeated_evidence_and_model_corroboration_language_cannot_inflate_confidence():
    event, observation = records()
    baseline = score(event, observation)
    repeated = replace(event, evidence=event.evidence * 3, corroboration_strength='100 independent confirmations')
    actual = score(repeated, observation)
    assert actual['score'] == baseline['score']
    assert actual['data_coverage'] == baseline['data_coverage']


def test_null_and_future_dates_are_missing_not_current_or_zero_observations():
    event, observation = records()
    complete = score(event, observation)
    missing = score(replace(event, event_date=None), observation)
    assert missing['data_coverage']['ratio'] < complete['data_coverage']['ratio']
    assert missing['score'] <= complete['score']
    future = score(event, replace(observation, source_published_at=NOW + timedelta(days=1)))
    assert next(f for f in future['factors'] if f['key'] == 'freshness')['points'] is None


def test_unbound_source_cannot_establish_registered_quality_or_freshness():
    event, observation = records()
    wrong = replace(observation, raw_evidence=replace(observation.raw_evidence, id='unrelated'))
    actual = score(event, wrong)
    assert actual['score'] is None
    assert {'source_reliability', 'freshness'} <= set(actual['data_coverage']['missing_factors'])


def test_source_change_invalidates_decision_and_old_publication_loses_freshness():
    event, observation = records()
    baseline = score(event, observation)
    changed = score(event, replace(observation, source_version=replace(observation.source_version, content_hash='a' * 64)))
    assert changed['decision_id'] != baseline['decision_id']
    stale = score(event, observation, NOW + timedelta(days=3))
    assert stale['score'] < baseline['score']
