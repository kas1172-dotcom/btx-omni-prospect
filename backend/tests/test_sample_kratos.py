from decimal import Decimal

from btx_omni.core.clock import as_of_datetime
from btx_omni.modules.scoring.public_inputs import public_signal_assessment
from btx_omni.providers.sample.kratos import context, payload


def test_j4_curated_research_not_invented_canonical_pursuit():
    data = payload()
    assert data['entity']['site'] == 'Auburn Hills, Michigan'
    assert data['history'][1]['superseded_by'] == data['signal_id']
    assert data['gates']['need'] == 'UNKNOWN'
    assert data['entity']['cage_uei'] is None
    assert data['contact_gap']['name'] is data['contact_gap']['email'] is None
    event, observation = context()
    result = public_signal_assessment(event, observation, now=as_of_datetime('2026-09-20'), freshness_hours=720)
    assert result['score'] == Decimal('63.75')
    assert result['band'] == 'MEDIUM'
    assert result['seller_recommendation_eligible'] is False
    assert next(f for f in result['factors'] if f['key'] == 'freshness')['contribution'] == 5
    assert not event.subject_entities  # No canonical prospect created ahead of publication gates.
    assert data['routes'][-1]['state'] == 'UNSUPPORTED_HYPOTHESIS'
