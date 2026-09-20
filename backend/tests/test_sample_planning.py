from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.planning_cases import planning_view


def test_j2_gap_is_not_forecast_and_three_sister_bu_sites_have_invoices():
    sample = enhance_environment(build_sample_environment())
    view = planning_view({'partnership_records': [], 'strategic_partnerships': []}, sample)
    context = view['business_unit_history'][0]
    assert context['forecast'] is context['target'] is None
    assert context['monthly_history_coverage'][0]['value_minor'] is None
    assert len({r['site_id'] for r in context['sister_business_unit_sites']}) == 3
    for row in context['sister_business_unit_sites']:
        assert row['evidence_ids']
        assert set(row['evidence_ids']) <= {r['invoice_id'] for r in sample.commercial_ledgers[row['account_id']]['invoices']}
    partner_ids = {r['account_id'] for r in view['strategic_partnerships']}
    assert partner_ids == {'demo-regional-medical-partner', 'demo-regional-aero-partner'}
    # A persisted removal must win over the default, including at version one.
    updated = planning_view({'partnership_records': [{'account_id': 'demo-regional-medical-partner', 'designated': False, 'version': 1}]}, sample)
    assert {r['account_id'] for r in updated['strategic_partnerships']} == {'demo-regional-aero-partner'}
