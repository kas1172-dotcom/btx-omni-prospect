from dataclasses import replace
from datetime import UTC, datetime, timedelta

from btx_omni.modules.scoring.public_inputs import (
    public_risk_assessment,
    public_signal_assessment,
)
from btx_omni.monitor.briefs import signal_brief
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.contracts import NormalizedClaim
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import EventType
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


def test_public_risk_is_separate_and_missing_assertions_do_not_become_zeroes():
    event, observation = records(title='KLA Corporation production delay')
    assert event.event_type is EventType.PRODUCTION_DELAY
    risk = public_risk_assessment(event, observation, now=NOW)
    assert risk['family'] == 'risk_severity'
    assert risk['score'] is None
    assert risk['status'] == 'INSUFFICIENT_EVIDENCE'
    assert risk['data_coverage']['present'] == 0
    assert risk['data_coverage']['applicable'] == 6
    brief = signal_brief(event, observation, freshness_hours=48, now=NOW)
    assert brief.risk_severity == risk
    assert brief.signal_confidence['score'] is not None


def test_scoped_source_claims_produce_reproducible_severity_and_disposition():
    event, observation = records(title='KLA Corporation production delay')
    evidence_id = event.evidence[0].evidence_id
    values = {
        'risk_impact_level': 'HIGH', 'risk_materiality_level': 'CRITICAL',
        'risk_imminence_level': 'HIGH', 'risk_persistence': 'MONTHS',
        'risk_breadth': 'PROGRAM', 'risk_reversibility': 'DIFFICULT',
    }
    claims = event.claims + tuple(
        NormalizedClaim(key, value, (evidence_id,), 'deterministic_structured_mapping', 'preserved source field')
        for key, value in values.items()
    )
    risk = public_risk_assessment(replace(event, claims=claims), observation, now=NOW)
    assert risk['score'] == 76.25
    assert risk['band'] == 'HIGH'
    assert risk['disposition'] == 'ESCALATE_NOW'
    assert risk['data_coverage']['present'] == risk['data_coverage']['applicable'] == 6
    copied = public_risk_assessment(replace(event, claims=claims + claims[1:]), observation, now=NOW)
    assert copied['score'] == risk['score']


def test_positive_event_does_not_receive_a_reverse_opportunity_score():
    event, observation = records()
    assert public_risk_assessment(event, observation, now=NOW) is None
