from decimal import Decimal

import pytest
from test_customer_health_v2 import scenario

from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.scoring.internal_risk import risk_inputs


def inputs(account):
    return risk_inputs(account, fulfillment_state(account, canonical_account_id='honeywell', revision='test'))


@pytest.mark.parametrize(('change', 'expected'), [('-0.251', 100), ('-0.25', 75), ('-0.10', 75), ('-0.099', 50), ('0', 25), ('0.099', 25), ('0.10', 0)])
def test_momentum_thresholds(change, expected):
    account = scenario()
    for row in account['monthly_commercial_history'][-6:-3]:
        row['bookings_minor'] = 100000
    for row in account['monthly_commercial_history'][-3:]:
        row['bookings_minor'] = int(100000 * (1 + Decimal(change)))
    assert inputs(account)['commercial_momentum'].points == expected


@pytest.mark.parametrize(('share', 'expected'), [(36, 100), (35, 75), (20, 75), (10, 50), (6, 25), (5, 0), (0, 0)])
def test_bu_concentration_not_customer_program_concentration(share, expected):
    account = scenario()
    account.pop('bu_revenue_exposure', None)
    assert inputs(account)['concentration'].points is None
    account['bu_revenue_exposure'] = {'record_id': 'bu-period-review', 'provenance': {'truth_class': 'POC_SCENARIO'},
        'business_unit_id': 'reviewed-bu', 'period_start': '2025-09-01', 'period_end': account['as_of'],
        'account_revenue_minor': share, 'bu_revenue_minor': 100}
    assert inputs(account)['concentration'].points == expected


def test_invoice_share_cannot_substitute_for_confirmed_friction():
    account = scenario()
    assert inputs(account)['friction'].points is None
    account['relationship_profile'].update(service_review_complete=True, payment_review_complete=True)
    account['invoices'] = []
    assert inputs(account)['friction'].points == 0
    account['service_events'] = [{'service_event_id': 'case', 'opened_date': account['as_of'], 'status': 'OPEN', 'critical': False, 'repeated': True}]
    assert inputs(account)['friction'].points == 50
    account['service_events'][0]['critical'] = True
    assert inputs(account)['friction'].points == 100


@pytest.mark.parametrize(('overdue', 'expected'), [(51, 100), (50, 75), (25, 75), (10, 50), (1, 25)])
def test_pipeline_uses_open_quote_decision_dates(overdue, expected):
    account = scenario()
    account['relationship_profile']['quote_review_complete'] = True
    account['quotes'] = [{'quote_id': 'late', 'status': 'OPEN', 'current_revision_id': 'rev-late', 'decision_date': '2026-01-01'},
        {'quote_id': 'future', 'status': 'OPEN', 'current_revision_id': 'rev-future', 'decision_date': '2027-01-01'}]
    account['quote_revisions'] = [{'quote_revision_id': 'rev-late', 'total_minor': overdue}, {'quote_revision_id': 'rev-future', 'total_minor': 100-overdue}]
    assert inputs(account)['pipeline'].points == expected
    account['quotes'][0].pop('decision_date')
    assert inputs(account)['pipeline'].points is None


def test_production_adapter_uses_rubric_inputs_without_mutating_records():
    account = scenario()
    projected = customer_decisions(account, account_id='honeywell', revision='test', current_customer=True)
    expected = inputs(account)
    for factor in projected['internal_commercial_risk']['factors']:
        assert factor['points'] == expected[factor['key']].points
    assert projected['internal_commercial_risk']['score'] is None
