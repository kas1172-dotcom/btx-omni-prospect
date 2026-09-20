from copy import deepcopy
from decimal import Decimal

from btx_omni.core.clock import as_of_datetime
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.scoring.families import overall_customer_risk
from btx_omni.modules.scoring.public_inputs import public_signal_assessment
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.scoring_cases import customer


def test_pwin_delivery_block_and_partial_range_are_live_pursuit_results():
    """66.25 uses 6.25+20+20+7.5+5+7.5: no fabricated named influencer.

    Incomplete PWIN has 18.75+15+14.25+10+10=68; 15 budget points missing.
    Requirement fit is the rubric's continuous 57/80, not an invented band.
    """
    sample = enhance_environment(build_sample_environment())
    account = sample.commercial_ledgers['demo-fictional-watch']
    result = customer_decisions(account, account_id=account['account_id'], revision='demo', current_customer=True,
        facility_ids=frozenset(f.id for f in sample.btx_facilities))['opportunities']
    normal, blocked, partial, low, stale, conflicting = result
    assert normal['pwin']['score'] == Decimal('66.25') and normal['pwin']['band'] == 'DEVELOPING'
    assert normal['qualification_status'] == 'YES'
    assert 'probability' in normal['pwin']['interpretation']
    assert normal['delivery_feasibility']['score'] == Decimal('72.50')
    assert normal['delivery_feasibility']['band'] == 'B'
    assert blocked['delivery_feasibility']['weighted_score'] == Decimal('78.75')
    assert blocked['delivery_feasibility']['weighted_band'] == 'B+'
    assert blocked['delivery_feasibility']['band'] == 'BLOCKED' and blocked['delivery_feasibility']['score'] is None
    assert partial['pwin']['score_range'] == {'low': Decimal(68), 'high': Decimal(83)}
    assert partial['pwin']['score'] is None
    assert low['opportunity_priority']['score'] < 50 and low['qualification_status'] == 'NO'
    for variant, state in [(stale, 'STALE'), (conflicting, 'CONFLICTING')]:
        factor = next(f for f in variant['delivery_feasibility']['factors'] if f['key'] == 'schedule_feasibility')
        assert factor['evidence_state'] == state and factor['points'] is None
        assert variant['delivery_feasibility']['score'] is None
    no_proof = deepcopy(account)
    no_proof['interactions'] = [r for r in no_proof['interactions'] if not r.get('buyer_role_verified')]
    assert customer_decisions(no_proof, account_id=account['account_id'], revision='demo', current_customer=True)['opportunities'][0]['pwin']['score'] is None


def test_coverage_85_requires_two_missing_factors_not_reweighting():
    account = customer('watch')
    account['relationship_profile'].pop('relationship_started_on')
    account['relationship_profile']['risk_history_review_complete'] = False
    result = customer_decisions(account, account_id=account['account_id'], revision='demo', current_customer=True)['customer_health']
    assert result['data_coverage']['ratio'] == Decimal('.85')
    assert set(result['data_coverage']['missing_factors']) == {'relationship_history', 'attached_risk_history'}
    assert result['score'] is None


def test_all_floors_and_linked_convergence_require_explicit_evidence():
    cases = [('public', 0, 85, (), (), 75), ('internal', 85, 0, (), (), 80),
             ('legal', 0, 0, (), ('fictional-legal-clearance-block',), 85),
             ('converged', 60, 60, ('fictional-linked-program-evidence',), (), 65)]
    for _, internal, public, links, block, target in cases:
        result = overall_customer_risk(current_customer=True, internal_score=Decimal(internal), public_score=Decimal(public),
            public_confirmed=True, convergence_evidence_ids=links, critical_override_evidence_ids=block)
        assert result['score'] == target
        assert result['execution_blocked'] == bool(block)
    plain = overall_customer_risk(current_customer=True, internal_score=Decimal(60), public_score=Decimal(60), public_confirmed=True)
    assert plain['score'] == 60 and plain['convergence_uplift'] == 0


def test_three_independent_origins_but_syndicated_pair_is_one():
    from btx_omni.providers.sample.rubric_examples import corroboration_context
    for origins, points in [(('origin-a', 'origin-b', 'origin-c'), 100), (('origin-a', 'origin-a'), 25)]:
        event, observation, sources = corroboration_context(origins)
        assert len({s['evidence_id'] for s in sources}) == len(origins)
        result = public_signal_assessment(event, observation, now=as_of_datetime(), freshness_hours=720)
        assert next(f for f in result['factors'] if f['key'] == 'independent_corroboration')['points'] == points


def test_live_what_if_lab_stores_calculated_floor_receipts_and_link_evidence():
    from btx_omni.providers.sample.rubric_examples import examples
    rows = examples()['examples']
    assert {k: rows[k]['overall']['score'] for k in ('public_floor', 'internal_floor', 'legal_floor', 'convergence')} == {
        'public_floor': 75, 'internal_floor': 80, 'legal_floor': 85, 'convergence': 80}
    assert rows['legal_floor']['overall']['execution_blocked']
    assert rows['convergence']['evidence'] and rows['convergence']['overall']['convergence_uplift'] == 5
    assert rows['coverage_85']['data_coverage']['ratio'] == Decimal('.85')
