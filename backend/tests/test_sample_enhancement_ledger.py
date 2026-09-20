from decimal import Decimal

from btx_omni.modules.commercial.ledger import KEYS, validate_commercial_account
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.providers.sample.enhancement import boeing_recovery


def test_j7_completion_requires_scoped_verified_proof():
    from btx_omni.providers.sample.enhancement import completion_gaps
    account = boeing_recovery()
    source = account['actions'][0]
    assert completion_gaps(source, account['fulfillment_plans']) == ('inspection_release', 'buyer_acceptance')
    proof = [{'completion_kind': key, 'verified': True, 'related_record_ids': [source['action_id']]}
             for key in source['required_completion_evidence']]
    assert completion_gaps(source, proof) == ()
    proof[0]['verified'] = False
    assert completion_gaps(source, proof) == ('inspection_release',)


def test_j7_opt_in_runtime_view_preserves_existing_canonical_ids():
    from btx_omni.providers.sample.environment import build_sample_environment
    from btx_omni.providers.sample.enhancement import enhance_environment
    base = build_sample_environment()
    result = enhance_environment(base)
    assert {a.id for a in base.accounts} <= {a.id for a in result.accounts}
    assert {a.id for a in base.programs} <= {a.id for a in result.programs}
    assert result.commercial_ledgers['boeing']['orders'][0]['total_minor'] == 28616000
    assert base.commercial_ledgers == {}


def test_j7_reconciles_exact_units_value_and_unaccepted_proposal():
    account = boeing_recovery()
    validate_commercial_account(account)
    state = fulfillment_state(account, canonical_account_id='boeing', revision='demo')
    totals = state['recorded_history_totals']
    assert (totals['ordered_quantity'], totals['shipped_quantity'], totals['remaining_quantity']) == (292, 146, 146)
    assert Decimal(totals['remaining_quantity'] * account['order_lines'][0]['unit_price_minor']) / 100 == Decimal('143080.00')
    assert account['fulfillment_plans'][0]['proposed_ship_date'] == '2026-09-26'
    assert account['fulfillment_plans'][0]['status'] == 'PENDING'
    assert account['fulfillment_plans'][0]['buyer_accepted'] is False
    assert any(c['type'] == 'UNACCEPTED_RECOVERY_PROPOSAL' for c in state['constraints'])
    assert account == boeing_recovery()


def test_new_commercial_rows_are_synthetic_and_date_relative():
    account = boeing_recovery(anchor='2026-10-20')
    for collection in KEYS:
        assert all(r['synthetic'] is True and r['data_mode'] == 'SAMPLE' for r in account[collection])
    assert account['orders'][0]['ordered_date'] == '2026-10-18'
    assert account['fulfillment_plans'][0]['proposed_ship_date'] == '2026-10-26'
    assert not account['contacts']
