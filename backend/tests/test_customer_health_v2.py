from copy import deepcopy
from decimal import Decimal

import pytest

from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.scoring.customer_health import health_inputs
from btx_omni.modules.scoring.families import FAMILIES, assess
from btx_omni.persistence.import_commercial_sample import load_release_sample


def scenario():
    account = deepcopy(load_release_sample()['accounts'][0])
    account['relationship_profile'] = {'record_id': 'authored-account-policy', 'provenance': {'truth_class': 'POC_ASSUMPTION'},
        'relationship_started_on': '2018-01-01', 'expected_touch_days': 30,
        'contact_review_complete': True, 'interaction_review_complete': True, 'risk_history_review_complete': True}
    account['service_events'] = []
    account['interactions'] = [{'interaction_id': 'authored-touch', 'date': '2026-08-30', 'two_way': True, 'meaningful_touch': True,
        'participant_role_ids': [r['role_target_id'] for r in account['role_targets']], 'real_person_ids': []}]
    for i, role in enumerate(account['role_targets']):
        role.update(contact_verified=True, verified_function=f'explicit-fictional-function-{i}')
    return account


def inputs(account):
    state = fulfillment_state(account, canonical_account_id='honeywell', revision='test')
    return health_inputs(account, state)


@pytest.mark.parametrize(('change', 'points'), [('0.10', 100), ('0', 75), ('-0.099', 50), ('-0.10', 25), ('-0.25', 25), ('-0.251', 0)])
def test_exact_trajectory_boundaries(change, points):
    account = scenario()
    for row in account['monthly_commercial_history'][-6:-3]:
        row['bookings_minor'] = 100000
    for row in account['monthly_commercial_history'][-3:]:
        row['bookings_minor'] = int(100000 * (1 + Decimal(change)))
    assert inputs(account)['commercial_trajectory'].points == points


def test_health_has_its_own_weights_and_trace_not_invoice_or_quote_conversion():
    account = scenario()
    original = deepcopy(account)
    factors = inputs(account)
    assert dict(FAMILIES['customer_health'].weights) == {'commercial_trajectory': 30, 'relationship_coverage': 20, 'engagement_cadence': 20, 'backlog_coverage': 15, 'relationship_history': 10, 'attached_risk_history': 5}
    assert factors['relationship_coverage'].points == 100
    assert factors['engagement_cadence'].points == 100
    assert factors['relationship_history'].points == 100
    assert factors['attached_risk_history'].points == 100
    score = assess('customer_health', subject_id='honeywell', as_of=account['as_of'], revision='test', inputs=factors, eligible=True)
    assert score['score'] is not None
    assert score['data_coverage']['ratio'] == 1
    assert all(f['evidence_ids'] for f in score['factors'])
    assert account == original


def test_unknown_contact_review_cannot_become_zero_and_notes_do_not_imply_engagement():
    account = scenario()
    account['relationship_profile'].pop('contact_review_complete')
    assert inputs(account)['relationship_coverage'].points is None
    account['relationship_profile']['contact_review_complete'] = True
    account['interactions'][0].pop('two_way')
    assert inputs(account)['relationship_coverage'].points == 25
    account['interactions'][0].pop('meaningful_touch')
    assert inputs(account)['engagement_cadence'].points == 0


def test_missing_months_or_zero_baseline_are_not_assumed_growth():
    account = scenario()
    account['monthly_commercial_history'].pop(-4)
    assert inputs(account)['commercial_trajectory'].points is None
    assert inputs(account)['backlog_coverage'].points is None
