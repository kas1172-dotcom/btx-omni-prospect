from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
    # Source 30 + parent identity 12.5 + 1/7 specificity * 20 + one origin
    # 3.75 + current fact 10. This is NOT sufficient site identity for promotion.
    assert decision['score'] == Decimal('59.11')
    assert decision['data_coverage']['ratio'] == 1
    assert decision['seller_recommendation_eligible'] is False
    assert len(decision['specificity_missing_fields']) == 6
    factors = {f['key']: f for f in decision['factors']}
    assert factors['independent_corroboration']['points'] == 25
    assert factors['source_reliability']['points'] == 100
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
    missing = score(replace(event, event_date=None, claims=tuple(c for c in event.claims if c.predicate != 'effective_date')), observation)
    assert missing['score'] == Decimal('56.25')
    assert missing['score_range']['low'] < complete['score_range']['low']
    assert 'effective_date' in missing['specificity_missing_fields']
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
    assert score(event, observation, NOW + timedelta(days=3))['score'] == baseline['score']
    stale = score(event, observation, NOW + timedelta(days=31))
    assert stale['score'] == Decimal('49.11')
    assert stale['score_range']['low'] < baseline['score_range']['low']


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
    assert brief.signal_confidence['score'] == Decimal('61.25')
    assert brief.signal_confidence['seller_recommendation_eligible'] is False


def test_scoped_source_claims_produce_reproducible_severity_and_disposition():
    event, observation = records(title='KLA Corporation production delay')
    evidence_id = event.evidence[0].evidence_id
    values = {
        'program_reduction_percent': '25', 'affected_revenue_share_percent': '50',
        'affected_backlog_share_percent': '25', 'days_until_effect': '60',
        'remaining_effect_days': '180', 'risk_breadth': 'PROGRAM', 'risk_mitigation': 'CONFIRMED_NO_PLAN',
    }
    claims = event.claims + tuple(
        NormalizedClaim(key, value, (evidence_id,), 'deterministic_structured_mapping', 'preserved source field')
        for key, value in values.items()
    )
    risk = public_risk_assessment(replace(event, claims=claims), observation, now=NOW)
    assert risk['score'] == Decimal('71.25')
    assert risk['band'] == 'HIGH'
    # Severity alone cannot prove high confidence or verified site identity.
    assert risk['disposition'] == 'VALIDATE_IMMEDIATELY'
    assert risk['data_coverage']['present'] == risk['data_coverage']['applicable'] == 6
    copied = public_risk_assessment(replace(event, claims=claims + claims[1:]), observation, now=NOW)
    assert copied['score'] == risk['score']


def test_positive_event_does_not_receive_a_reverse_opportunity_score():
    event, observation = records()
    assert public_risk_assessment(event, observation, now=NOW) is None
