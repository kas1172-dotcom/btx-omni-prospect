"""Leaf observations for qualified fictional pursuits, never invented people."""
import json

from btx_omni.core.clock import relative_date
from btx_omni.modules.scoring.account_attractiveness import FACTORS
from btx_omni.providers.sample.enhancement import synthetic_record


def add_pursuit_cases(account):
    opportunity = account['opportunities'][0]
    oid = opportunity['opportunity_id']
    role = account['role_targets'][0]['role_target_id']
    proof_id = oid + ':buyer-role-document'
    proof = synthetic_record(interaction_id=proof_id, date=account['as_of'], real_person_ids=[], participant_role_ids=[role],
        related_record_ids=[oid], source_document_id=account['rfqs'][-1]['rfq_id'], buyer_role_verified=True,
        meaningful_touch=False, two_way=False,
        notes='Fictional RFQ identifies the procurement function, not a person. No two-way conversation or warm introduction is asserted.')
    account['interactions'].append(proof)
    opportunity.update(qualified_buyer_role_id=role, buyer_qualification_evidence_ids=[proof_id])
    pwin = {
        'buyer_access': {'state': 'VERIFIED_ROLE_NO_INTERACTION'},
        'competitive_position': {'state': 'BUYER_DOCUMENTED_SOLE_SOURCE'},
        'requirement_fit': {'noncritical_met': 10, 'noncritical_total': 10, 'critical_requirements_pass': True},
        'budget_process': {'state': 'BUDGET_CONFIRMED'},
        'price_competitiveness': {'quoted_minor': 85000, 'buyer_target_minor': 81000},
        'track_record': {'state': 'ONE_ACCEPTED_SAME_REQUIREMENTS'},
    }
    delivery = {
        'capability_match': {'state': 'ONE_FUNDED_DATED_NONCRITICAL_GAP'},
        'schedule_feasibility': {'net_available_hours': 110, 'required_hours': 100},
        'material_readiness': {'most_constrained_critical_material_days_early': 14},
        'quality_certification': {'state': 'VALID_BUYER_QUALIFICATION_SCHEDULED'},
        'margin': {'quoted_minor': 85000, 'estimated_total_cost_minor': 76500},
        'coordination': {'state': 'ONE_DATE_UNKNOWN'},
    }
    opportunity['scoring_inputs'] = {family: {key: synthetic_record(**raw, opportunity_id=oid,
        facility_id=opportunity['delivery_facility_id'], reviewed_as_of=account['as_of'], evidence_ids=[oid],
        narrative='Authored fictional scope review; inspect the numeric input, not an AI estimate.') for key, raw in rows.items()}
        for family, rows in [('pwin', pwin), ('delivery_feasibility', delivery)]}
    blocked = json.loads(json.dumps(opportunity).replace(oid, oid + ':blocked'))
    blocked['delivery_facility_id'] = 'a1j-san-jose'
    for row in blocked['scoring_inputs']['delivery_feasibility'].values():
        row['facility_id'] = 'a1j-san-jose'
    values = blocked['scoring_inputs']['delivery_feasibility']
    values['capability_match']['state'] = 'ALL_AVAILABLE'
    values['material_readiness']['most_constrained_critical_material_days_early'] = 30
    values['quality_certification']['state'] = 'MANDATORY_UNAVAILABLE_BY_START'
    values['margin']['estimated_total_cost_minor'] = 59500
    values['coordination']['state'] = 'ALL_OWNERS_AND_DATES'
    blocked['title'] = 'Fictional alternate solution — mandatory certification unavailable'
    incomplete = json.loads(json.dumps(opportunity).replace(oid, oid + ':incomplete'))
    values = incomplete['scoring_inputs']['pwin']
    values.pop('budget_process')
    values['buyer_access']['state'] = 'EVALUATION_COMMITTEE_TWO_WAY'
    values['competitive_position']['state'] = 'ELIGIBLE_INCUMBENT'
    values['requirement_fit'].update(noncritical_met=57, noncritical_total=80)
    values['price_competitiveness']['buyer_target_minor'] = 100000
    values['track_record']['state'] = 'TWO_ACCEPTED_SAME_REQUIREMENTS'
    incomplete['title'] = 'Fictional incomplete readiness review — budget evidence missing'
    committee = oid + ':committee-role'
    account['role_targets'].append(synthetic_record(role_target_id=committee, verified_function='procurement', contact_verified=True,
        name=None, email=None, title='Fictional procurement evaluation committee function; not a named person'))
    incomplete['qualified_buyer_role_id'] = committee
    for row in (blocked, incomplete):
        row['buyer_qualification_evidence_ids'] = [proof_id]
        proof['related_record_ids'].append(row['opportunity_id'])
        account['opportunities'].append(row)
    committee_proof = synthetic_record(interaction_id=oid + ':committee-review', date=account['as_of'], real_person_ids=[],
        participant_role_ids=[committee], related_record_ids=[incomplete['opportunity_id']], source_document_id=account['rfqs'][-1]['rfq_id'],
        buyer_role_verified=True, two_way=True, meaningful_touch=False,
        notes='Authored fictional committee-function exchange for the alternate incomplete case; budget question remains unanswered. No named person or real conversation.')
    account['interactions'].append(committee_proof)
    incomplete['buyer_qualification_evidence_ids'] = [committee_proof['interaction_id']]
    low = json.loads(json.dumps(opportunity).replace(oid, oid + ':low'))
    low.update(title='Fictional unsuitable one-off pursuit', stage='DISCOVERY', qualified_buyer_role_id=None)
    low_bins = {}
    for factor in FACTORS:
        if factor.subfactors:
            for leaf in factor.subfactors:
                low_bins[factor.key + '.' + leaf.rubric.key] = min(leaf.rubric.bins, key=lambda b: b.points).key
        else:
            low_bins[factor.key] = min(factor.single_rubric.bins, key=lambda b: b.points).key
    low_bins['btx_commercial_adjacency'] = 'EXISTING_ONE_BU_ACTIVE'
    for row in low['score_observations']:
        row['bin'] = low_bins[row['path']]
    low['qualification_evidence']['sourced_dated_need'] = False
    account['opportunities'].append(low)
    for variant in ('stale', 'conflicting'):
        other = json.loads(json.dumps(opportunity).replace(oid, oid + ':' + variant))
        other['title'] = 'Fictional alternate solution with ' + variant + ' capacity evidence'
        raw = other['scoring_inputs']['delivery_feasibility']['schedule_feasibility']
        raw['reviewed_as_of'] = relative_date(-3, anchor=account['as_of']) if variant == 'stale' else account['as_of']
        raw['evidence_state'] = variant.upper()
        account['opportunities'].append(other)
    return account
