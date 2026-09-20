"""Regression tests for amended R1–R8; no public facts are asserted here."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from test_customer_health_v2 import scenario, inputs as health
from test_public_signal_assessment import NOW, records
from btx_omni.modules.scoring.families import FactorInput, assess, customer_risk_projection
from btx_omni.modules.scoring.public_inputs import public_risk_assessment
from btx_omni.modules.scoring.public_rules import freshness_points
from btx_omni.monitor.contracts import NormalizedClaim


@pytest.mark.parametrize(('age', 'points'), [('7.5', 100), ('7.6', 75), ('15.0', 75), ('15.1', 50), ('30.0', 50), ('30.1', 0)])
def test_exact_freshness_boundaries(age, points):
    assert freshness_points(Decimal(age) * 24, 720) == points


@pytest.mark.parametrize('state', ['STALE', 'UNKNOWN', 'CONFLICTING'])
def test_unusable_factor_keeps_history_but_never_a_numeric_contribution(state):
    item = FactorInput(Decimal(100), ('fictional-evidence',), 'Historical value retained.', evidence_state=state)
    result = assess('risk_severity', subject_id='fictional', as_of='2026-09-20', revision='1', inputs={'impact': item}, eligible=True)
    assert result['score'] is None
    assert result['score_range'] == {'low': 0, 'high': 100}
    assert result['factors'][0]['points'] is None
    assert result['factors'][0]['evidence_ids'] == ('fictional-evidence',)
    assert result['rule_version'] == 'BTX_SCORING_RUBRIC_V2.0'


def test_stale_public_risk_is_unknown_not_old_numeric_severity():
    event, observation = records(title='Fictional audit scenario facility closure')
    eid = event.evidence[0].evidence_id
    facts = {'risk_direction': 'NEGATIVE', 'risk_condition': 'FACILITY_CLOSURE',
             'affected_revenue_share_percent': '30', 'affected_backlog_share_percent': '25',
             'days_until_effect': '0', 'remaining_effect_days': '400',
             'risk_breadth': 'MULTIPLE_BUSINESS_UNITS', 'risk_mitigation': 'PLAN_NOT_STARTED'}
    event = replace(event, claims=event.claims + tuple(NormalizedClaim(k, v, (eid,), 'reviewed_source_extraction', 'fictional test only') for k, v in facts.items()))
    current = public_risk_assessment(event, observation, now=NOW)
    assert current['score'] == Decimal('76.25')
    stale = public_risk_assessment(event, observation, now=NOW + timedelta(days=31))
    assert stale['evidence_state'] == 'STALE'
    assert stale['score'] is None
    assert stale['score_range'] == {'low': 0, 'high': 100}
    assert stale['disposition'] == 'INSUFFICIENT_EVIDENCE'


def test_internal_snapshot_expires_not_historical_transactions():
    account = scenario()
    account['snapshot_observed_as_of'] = '2026-08-28'
    result = assess('customer_health', subject_id='fictional', as_of=account['as_of'], revision='1', inputs=health(account), eligible=True)
    assert result['score'] is None
    assert {'commercial_trajectory', 'backlog_coverage', 'attached_risk_history'} <= set(result['data_coverage']['missing_factors'])


def test_wrapper_requires_explicit_convergence_and_critical_evidence():
    kwargs = dict(account_id='fictional', current_customer=True, internal_decision={'score': 65}, signal_briefs=(), monitoring_complete=True)
    assert customer_risk_projection(**kwargs)['overall_customer_risk']['convergence_uplift'] == 0
    result = customer_risk_projection(**kwargs, critical_override_evidence_ids=('confirmed-safety-shutdown',))['overall_customer_risk']
    assert result['score'] == 85
    assert result['execution_blocked'] is True
