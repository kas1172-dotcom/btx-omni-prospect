from decimal import Decimal

import pytest

from btx_omni.core.clock import as_of_datetime
from btx_omni.modules.scoring.public_inputs import public_signal_assessment
from btx_omni.providers.sample.rubric_examples import award_context


@pytest.mark.parametrize(('age', 'freshness', 'total', 'state'), [
    ('3', '10', '88.75', 'CURRENT'), ('9', '7.5', '86.25', 'CURRENT'),
    ('7.5', '10', '88.75', 'CURRENT'), ('7.6', '7.5', '86.25', 'CURRENT'),
    ('15.0', '7.5', '86.25', 'CURRENT'), ('15.1', '5', '83.75', 'CURRENT'),
    ('30.0', '5', '83.75', 'CURRENT'), ('30.1', '0', None, 'STALE'),
])
def test_single_primary_sam_style_source_exact_boundaries(age, freshness, total, state):
    result = public_signal_assessment(*award_context(age), now=as_of_datetime(), freshness_hours=720)
    assert result['score'] == (Decimal(total) if total is not None else None)
    assert result['band'] == ('HIGH' if total is not None else 'INSUFFICIENT_EVIDENCE')
    assert next(f for f in result['factors'] if f['key'] == 'freshness')['contribution'] == Decimal(freshness)
    assert result['evidence_state'] == state
    assert result['synthetic'] is True and result['seller_recommendation_eligible'] is False
    assert all(f['truth_class'] == 'POC_SCENARIO' for f in result['factors'])
    if state == 'STALE':
        assert result['score_range'] == {'low': 0, 'high': 90}
        assert all(f['evidence_ids'] for f in result['factors'])
