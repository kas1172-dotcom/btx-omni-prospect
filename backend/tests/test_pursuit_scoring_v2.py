from decimal import Decimal

import pytest
from test_customer_health_v2 import scenario

from btx_omni.modules.scoring.families import FAMILIES
from btx_omni.modules.scoring.pursuit_inputs import factor_points, pursuit_inputs


@pytest.mark.parametrize(('key', 'raw', 'expected'), [
    ('price_competitiveness', {'quoted_minor': 95, 'buyer_target_minor': 100}, 100),
    ('price_competitiveness', {'quoted_minor': 100, 'buyer_target_minor': 100}, 75),
    ('price_competitiveness', {'quoted_minor': 110, 'buyer_target_minor': 100}, 50),
    ('price_competitiveness', {'quoted_minor': 125, 'buyer_target_minor': 100}, 25),
    ('price_competitiveness', {'quoted_minor': 126, 'buyer_target_minor': 100}, 0),
    ('price_competitiveness', {'quoted_minor': 100, 'buyer_target_minor': 0}, None),
    ('requirement_fit', {'noncritical_met': 3, 'noncritical_total': 4}, 75),
    ('requirement_fit', {'noncritical_met': 5, 'noncritical_total': 4}, None),
    ('schedule_feasibility', {'net_available_hours': 125, 'required_hours': 100}, 100),
    ('schedule_feasibility', {'net_available_hours': 110, 'required_hours': 100}, 75),
    ('schedule_feasibility', {'net_available_hours': 100, 'required_hours': 100}, 50),
    ('schedule_feasibility', {'net_available_hours': 90, 'required_hours': 100}, 25),
    ('schedule_feasibility', {'net_available_hours': 89, 'required_hours': 100}, 0),
    ('schedule_feasibility', {'net_available_hours': 'NaN', 'required_hours': 100}, None),
    ('material_readiness', {'most_constrained_critical_material_days_early': 30}, 100),
    ('material_readiness', {'most_constrained_critical_material_days_early': 14}, 75),
    ('material_readiness', {'most_constrained_critical_material_days_early': 1}, 50),
    ('material_readiness', {'most_constrained_critical_material_days_early': 0}, 25),
    ('material_readiness', {'most_constrained_critical_material_days_early': -1}, 0),
    ('margin', {'quoted_minor': 100, 'estimated_total_cost_minor': 70}, 100),
    ('margin', {'quoted_minor': 100, 'estimated_total_cost_minor': 80}, 75),
    ('margin', {'quoted_minor': 100, 'estimated_total_cost_minor': 90}, 50),
    ('margin', {'quoted_minor': 100, 'estimated_total_cost_minor': 100}, 25),
    ('margin', {'quoted_minor': 100, 'estimated_total_cost_minor': 101}, 0),
])
def test_normative_numeric_bins(key, raw, expected):
    assert factor_points(key, raw) == expected


def test_family_weights_match_v2_not_old_provisional_rubrics():
    assert dict(FAMILIES['pwin'].weights) == {'buyer_access': 25, 'competitive_position': 20, 'requirement_fit': 20, 'budget_process': 15, 'price_competitiveness': 10, 'track_record': 10}
    assert dict(FAMILIES['delivery_feasibility'].weights) == {'capability_match': 30, 'schedule_feasibility': 25, 'material_readiness': 15, 'quality_certification': 15, 'margin': 10, 'coordination': 5}


def test_scope_source_and_critical_checks_are_independent_of_factor_points():
    account = scenario()
    opportunity = account['opportunities'][0]
    line = next(r for r in account['quote_lines'] if r['quote_revision_id'] == opportunity['quote_revision_id'] and r['component_id'] == opportunity['component_id'])
    raw = {'opportunity_id': opportunity['opportunity_id'], 'reviewed_as_of': account['as_of'],
        'evidence_ids': [line['quote_line_id']], 'noncritical_met': 4, 'noncritical_total': 4}
    opportunity['scoring_inputs'] = {'pwin': {'requirement_fit': raw}}
    inputs, blocks, missing = pursuit_inputs(account, opportunity, 'pwin')
    assert inputs['requirement_fit'].points == Decimal(100)
    assert missing and not blocks
    raw['critical_requirements_pass'] = False
    assert pursuit_inputs(account, opportunity, 'pwin')[1]
    raw['critical_requirements_pass'] = True
    assert not pursuit_inputs(account, opportunity, 'pwin')[2]
    raw['opportunity_id'] = 'another-pursuit'
    assert pursuit_inputs(account, opportunity, 'pwin')[0]['requirement_fit'].points is None
    raw['opportunity_id'] = opportunity['opportunity_id']
    raw['evidence_ids'] = ['other-account-evidence']
    assert pursuit_inputs(account, opportunity, 'pwin')[0]['requirement_fit'].points is None


def test_complete_qualified_pursuit_uses_real_projection_and_blocks_override_score():
    from btx_omni.modules.scoring.account_attractiveness import FACTORS
    from btx_omni.modules.scoring.commercial_decisions import opportunity_decisions

    account = scenario()
    opportunity = account['opportunities'][0]
    oid = opportunity['opportunity_id']
    scope = {'opportunity_id': oid, 'reviewed_as_of': account['as_of'], 'evidence_ids': [oid]}
    opportunity['score_observations'] = [
        {**scope, 'path': f'{factor.key}.{child.rubric.key}', 'bin': child.rubric.bins[0].key}
        for factor in FACTORS for child in factor.subfactors
    ] + [{**scope, 'path': factor.key, 'bin': factor.single_rubric.bins[0].key}
         for factor in FACTORS if not factor.subfactors]
    opportunity['qualification_evidence'] = {**scope, 'identity_and_site_confirmed': True,
        'sourced_dated_need': True, 'scoped_component_and_external_sourcing': True,
        'no_disqualifiers': True, 'program_current': True, 'review_window_on': '2026-09-10',
        'essential_assertion_confidence': dict.fromkeys(['identity', 'need', 'capability', 'timing'], 75)}
    opportunity['stage'] = 'QUALIFIED'
    opportunity['qualified_buyer_contact_id'] = 'isolated-fictional-buyer'
    interaction = account['interactions'][0]
    interaction['real_person_ids'] = ['isolated-fictional-buyer']
    interaction['related_record_ids'] = [oid]
    opportunity['buyer_qualification_evidence_ids'] = [interaction['interaction_id']]
    line = next(r for r in account['quote_lines'] if r['quote_revision_id'] == opportunity['quote_revision_id'] and r['component_id'] == opportunity['component_id'])
    line['technical_requirements'] = {'test_only': 'Isolated scoped requirement'}
    opportunity['delivery_facility_id'] = 'isolated-facility'
    opportunity['scoring_inputs'] = {
        'pwin': {key: {**scope, **values} for key, values in {
            'buyer_access': {'state': 'DECISION_AUTHORITY_TWO_WAY'},
            'competitive_position': {'state': 'BUYER_DOCUMENTED_SOLE_SOURCE'},
            'requirement_fit': {'critical_requirements_pass': True, 'noncritical_met': 4, 'noncritical_total': 4},
            'budget_process': {'state': 'BUDGET_DATE_PROCESS_CONFIRMED'},
            'price_competitiveness': {'quoted_minor': 95, 'buyer_target_minor': 100},
            'track_record': {'state': 'TWO_ACCEPTED_SAME_REQUIREMENTS'},
        }.items()},
        'delivery_feasibility': {key: {**scope, 'facility_id': 'isolated-facility', **values} for key, values in {
            'capability_match': {'state': 'ALL_AVAILABLE'},
            'schedule_feasibility': {'net_available_hours': 125, 'required_hours': 100},
            'material_readiness': {'most_constrained_critical_material_days_early': 30},
            'quality_certification': {'state': 'VALID_THROUGH_DELIVERY_BUYER_APPROVED'},
            'margin': {'quoted_minor': 100, 'estimated_total_cost_minor': 70},
            'coordination': {'state': 'ALL_OWNERS_AND_DATES'},
        }.items()},
    }
    def calculate():
        return opportunity_decisions(account, account_id='isolated-account', revision='test', facility_ids=frozenset({'isolated-facility'}))[0]
    result = calculate()
    assert result['gates']['durable_best_bet'] is True
    assert result['opportunity_priority']['score'] == result['pwin']['score'] == result['delivery_feasibility']['score'] == 100
    opportunity['scoring_inputs']['pwin']['requirement_fit']['critical_requirements_pass'] = False
    opportunity['scoring_inputs']['delivery_feasibility']['quality_certification']['state'] = 'MANDATORY_UNAVAILABLE_BY_START'
    blocked = calculate()
    assert blocked['pwin']['status'] == blocked['delivery_feasibility']['status'] == 'BLOCKED'
    assert blocked['pwin']['score'] is None and blocked['delivery_feasibility']['score'] is None
