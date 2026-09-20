"""Qualified and Durable are independent three-state classifications (v2)."""
from datetime import date
from decimal import Decimal

from btx_omni.modules.commercial.evidence import evidence_supports_opportunity


def combine(values):
    return 'NO' if False in values else 'UNKNOWN' if None in values else 'YES'


def opportunity_gates(account: dict, opportunity: dict, inputs, priority: dict) -> dict:
    raw = opportunity.get('qualification_evidence', {})
    ids = raw.get('evidence_ids', [])
    valid = (raw.get('opportunity_id') == opportunity['opportunity_id'] and raw.get('reviewed_as_of') == account['as_of']
             and ids and all(evidence_supports_opportunity(account, identity, opportunity) for identity in ids))
    evidence = raw if valid else {}
    selections = inputs.selections
    def assertion(name):
        value = evidence.get(name)
        return value if type(value) is bool else None
    confidence = evidence.get('essential_assertion_confidence', {})
    confidence_values = [confidence.get(name) for name in ('identity', 'need', 'capability', 'timing')]
    confidence_known = all(type(value) in (int, float) and 0 <= value <= 100 for value in confidence_values)
    try:
        days = (date.fromisoformat(evidence['review_window_on']) - date.fromisoformat(account['as_of'])).days
        timing = 0 <= days <= 180
    except (KeyError, ValueError, TypeError):
        timing = None
    capability = []
    for key, allowed in [('material_match', {'ROUTINE', 'EXTENDED_ANALOGOUS'}), ('process_tolerance_match', {'ROUTINE', 'EDGE_BUT_ANALOGOUS'}), ('certification_compliance_fit', {'ALL_MET', 'MINOR_GAP'})]:
        value = selections.get('btx_manufacturing_fit.' + key)
        capability.append(None if value is None else value in allowed)
    checks = {'identity': assertion('identity_and_site_confirmed'),
        'evidence': all(value >= 70 for value in confidence_values) if confidence_known else None,
        'need': assertion('sourced_dated_need'),
        'capability': False if False in capability else None if None in capability else True,
        'addressable_work': assertion('scoped_component_and_external_sourcing'), 'timing': timing,
        'no_disqualifiers': assertion('no_disqualifiers')}
    durable = {}
    for key, allowed in [('expected_production_horizon', {'TEN_PLUS_YEARS', 'FIVE_TO_NINE_YEARS'}),
        ('repeat_production_pattern', {'ESTABLISHED_RECURRING', 'MULTIPLE_BATCHES_NOT_LOCKED'}),
        ('commitment_strength', {'FUNDED_AWARDED_CONTRACTED', 'BUDGETED_CREDIBLE_FUNDING'}),
        ('industry_specific_maturity_evidence', {'STRONG_EVIDENCE', 'PARTIAL_CREDIBLE'})]:
        value = selections.get('program_durability.' + key)
        durable[key] = None if value is None else value in allowed
    durable['program_current'] = assertion('program_current')
    qualified, durable_state = combine(list(checks.values())), combine(list(durable.values()))
    score = priority['score']
    return {'qualified': qualified, 'durable': durable_state, 'qualification_checks': checks, 'durability_checks': durable,
        'evidence_ids': ids if valid else [],
        'qualified_and_durable': qualified == durable_state == 'YES',
        'durable_best_bet': qualified == durable_state == 'YES' and score is not None and score >= Decimal(75)
            and confidence_known and min(confidence_values) >= 70 and priority['data_coverage']['ratio'] == 1}
