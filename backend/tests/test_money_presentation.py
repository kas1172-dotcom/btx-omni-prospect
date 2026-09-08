import json
from copy import deepcopy
from pathlib import Path

from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.commercial.money import model_money_projection


def test_money_projection_is_exact_nested_null_preserving_and_non_mutating():
    source = {'currency': 'USD', 'revenue_minor': 426489532, 'rows': [
        {'value_minor': -105, 'unknown_minor': None, 'quantity': 146},
        {'currency': 'JPY', 'value_minor': 400},
    ]}
    before = deepcopy(source)
    result = model_money_projection(source, currency='USD')
    assert source == before
    assert result['revenue_money'] == {'currency': 'USD', 'major_units': '4264895.32', 'display': 'USD 4,264,895.32'}
    assert result['rows'][0]['value_money']['major_units'] == '-1.05'
    assert result['rows'][0]['unknown_money'] is None and result['rows'][0]['quantity'] == 146
    assert result['rows'][1]['value_money']['major_units'] is None
    assert result['rows'][1]['value_money']['currency'] == 'JPY'


def test_actual_eaton_shipment_values_reconcile_without_inventing_acceptance():
    root = Path(__file__).resolve().parents[2]
    package = json.loads((root / 'docs/research/enriched_commercial_sample.json').read_text())
    source = next(a for a in package['accounts'] if a['account_id'] == 'ACC-EATON')
    result = fulfillment_state(source, canonical_account_id='eaton', revision='source-test')
    assert result['recorded_history_totals']['shipped_unaccepted_quantity'] == 187
    assert result['recorded_history_totals']['shipped_unaccepted_value_minor'] == 23911800
    shipments = {s['shipment_id']: s for line in result['lines'] for s in line['shipments']}
    assert shipments['SHP2-EATON-13-1-1']['unaccepted_value_minor'] == 19536000
    assert shipments['SHP2-EATON-13-2-1']['unaccepted_value_minor'] == 4375800
    assert shipments['SHP2-EATON-13-1-1']['accepted_quantity'] == 0
    assert shipments['SHP2-EATON-13-2-1']['accepted_quantity'] == 0
