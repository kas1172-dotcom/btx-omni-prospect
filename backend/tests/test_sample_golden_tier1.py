from decimal import Decimal
import pytest

from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.providers.sample.scoring_cases import customer, add_expansion


def decide(case):
    account = customer(case)
    validate_commercial_account(account)
    return customer_decisions(account, account_id=account['account_id'], revision='sample', current_customer=True)


def test_internal_risk_52_5_from_reconciled_transactions():
    result = decide('risk')['internal_commercial_risk']
    assert result['score'] == Decimal('52.50')
    assert result['band'] == 'MODERATE'
    assert [f['contribution'] for f in result['factors']] == [Decimal(x) for x in ('22.5', '10', '7.5', '7.5', '2.5', '2.5')]


def test_health_watch_60_from_reconciled_transactions():
    result = decide('watch')['customer_health']
    assert result['score'] == Decimal('60.00')
    assert result['band'] == 'WATCH'


@pytest.mark.parametrize(('case', 'band'), [('healthy', 'HEALTHY'), ('at-risk', 'AT_RISK'), ('critical', 'CRITICAL')])
def test_health_distribution(case, band):
    assert decide(case)['customer_health']['band'] == band


def test_opportunity_81_75_with_independent_qualified_durable_gates():
    """Target reachable, but not the original illustrative outer-factor breakdown.

    Exact leaf solution yields 23.1 + 19.75 + 12 + 8.4 + 10 + 8.5.
    Band tables govern over the rubric example's illustrative contributions.
    """
    account = add_expansion(customer('watch'), facility_id='fictional-site')
    result = customer_decisions(account, account_id=account['account_id'], revision='sample', current_customer=True)['opportunities'][0]
    assert result['opportunity_priority']['score'] == Decimal('81.75')
    assert result['qualification_status'] == result['durability_status'] == 'YES'
    assert result['gates']['durable_best_bet'] is True


def test_public_internal_and_combined_risk_are_separate():
    from btx_omni.core.clock import as_of_datetime
    from btx_omni.monitor.briefs import signal_brief
    from btx_omni.modules.scoring.families import customer_risk_projection
    from btx_omni.providers.sample.risk_cases import risk_context
    event, observation = risk_context()
    brief = signal_brief(event, observation, freshness_hours=720, now=as_of_datetime())
    assert brief.risk_severity['score'] == Decimal('76.25')
    assert brief.risk_severity['band'] == 'HIGH'
    assert brief.risk_severity['disposition'] == 'ESCALATE_NOW'
    assert brief.signal_confidence['synthetic'] is True
    internal = decide('risk')['internal_commercial_risk']
    result = customer_risk_projection(account_id='demo-fictional-risk', current_customer=True, internal_decision=internal, signal_briefs=(brief,))
    combined = result['overall_customer_risk']
    assert combined['score'] == Decimal('62.00')
    assert combined['convergence_uplift'] == 0 and combined['applicable_floors'] == []


def test_action_queue_classes_dominate_raw_score():
    from btx_omni.modules.scoring.action_priority import rank_actions
    rows = [
        {'id': 'risk', 'account_id': 'fictional-risk', 'status': 'OPEN', 'underlying_decision': {'score': Decimal('76.25'), 'disposition': 'ESCALATE_NOW'}},
        {'id': 'rfq', 'account_id': 'fictional-risk', 'status': 'OPEN', 'underlying_decision': {'score': 94}},
        {'id': 'cooling', 'account_id': 'fictional-risk', 'owner_id': None, 'status': 'OPEN', 'underlying_decision': {'score': 60}},
        {'id': 'safety', 'account_id': 'fictional-other', 'status': 'OPEN', 'confirmed_block': True, 'underlying_decision': {'score': 1}},
    ]
    assert [r['id'] for r in rank_actions(rows)] == ['safety', 'risk', 'rfq', 'cooling']
