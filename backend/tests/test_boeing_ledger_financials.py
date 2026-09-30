"""Reconciled SAMPLE Boeing financial history, never actual BTX transactions."""

from datetime import date
from decimal import Decimal

from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment


def test_boeing_financials_are_labeled_and_reconcile_to_accepted_work():
    account = enhance_environment(build_sample_environment()).commercial_ledgers['boeing']
    validate_commercial_account(account)
    months = account['monthly_commercial_history']
    assert len(months) == 12
    assert all(row['bookings_minor'] > 0 and row['revenue_minor'] > 0 for row in months)
    prior = sum(row['bookings_minor'] for row in months[-6:-3])
    recent = sum(row['bookings_minor'] for row in months[-3:])
    assert Decimal(0) < Decimal(recent - prior) / prior < Decimal('.10')
    assert 3 <= len([row for row in account['orders'] if row['status'] == 'FULFILLED']) <= 5

    accepted = {row['acceptance_id']: row for row in account['acceptances']}
    shipped = {row['shipment_id']: row for row in account['shipments']}
    invoiced = {row['revenue_event_id']: row for row in account['invoices']}
    paid = {row['invoice_id']: row for row in account['payments']}
    assert all(row['acceptance_id'] in accepted
               and accepted[row['acceptance_id']]['shipment_id'] in shipped
               and row['revenue_event_id'] in invoiced
               and invoiced[row['revenue_event_id']]['invoice_id'] in paid
               for row in account['revenue_events'])
    assert any(date.fromisoformat(row['paid_date']) > date.fromisoformat(paid_invoice['due_date'])
               for row in account['payments']
               for paid_invoice in account['invoices'] if paid_invoice['invoice_id'] == row['invoice_id'])
    assert not any(row.get('critical') and row['status'] not in {'RESOLVED', 'CLOSED'}
                   for row in account['service_events'])
    assert len([row for row in account['service_events'] if row['status'] == 'RESOLVED']) == 2
    assert account['relationship_profile']['synthetic'] is True
    assert account['bu_revenue_exposure']['synthetic'] is True

    authored = [row for collection in account.values() if isinstance(collection, list)
                for row in collection if isinstance(row, dict)
                and any(str(value).startswith(('boeing:sample-', 'sample:boeing:', 'boeing:relationship-profile:sample',
                                                'boeing:bu-revenue-exposure:sample'))
                        for value in row.values() if isinstance(value, str))]
    assert authored
    assert all(row['data_mode'] == 'SAMPLE' and row['synthetic'] is True
               and row.get('source', '').startswith('Authored SAMPLE') for row in authored)
    assert all(row['source'].startswith('Authored SAMPLE') for row in months)


def test_boeing_health_and_risk_have_complete_numeric_assessments():
    environment = enhance_environment(build_sample_environment())
    account = environment.commercial_ledgers['boeing']
    decision = customer_decisions(account, account_id='boeing',
        revision=environment.commercial_revision, current_customer=True,
        facility_ids=frozenset(row.id for row in environment.btx_facilities))
    for family in ('customer_health', 'internal_commercial_risk'):
        assessment = decision[family]
        assert assessment['status'] == 'SCORED'
        assert assessment['score'] is not None and assessment['band']
        assert all(factor['points'] is not None for factor in assessment['factors'])
