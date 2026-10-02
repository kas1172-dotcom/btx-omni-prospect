"""One explicitly synthetic Boeing J7 pursuit; no real buyer or award is claimed."""

from btx_omni.core.clock import relative_date
from btx_omni.providers.sample.classifications import (
    authored_bin_row,
    authored_input_row,
)
from btx_omni.providers.sample.enhancement import synthetic_record

OPPORTUNITY_ID = 'demo:j7:boeing:recovery-expansion'

SCORE_BINS = {
    'program_durability.expected_production_horizon': 'UNDER_TWO_YEARS_OR_ONE_OFF',
    'program_durability.repeat_production_pattern': 'SINGLE_DEFINED_RUN',
    'program_durability.commitment_strength': 'FUNDED_AWARDED_CONTRACTED',
    'program_durability.industry_specific_maturity_evidence': 'PARTIAL_CREDIBLE',
    'btx_manufacturing_fit.material_match': 'ROUTINE',
    'btx_manufacturing_fit.process_tolerance_match': 'ROUTINE',
    'btx_manufacturing_fit.certification_compliance_fit': 'MINOR_GAP',
    'btx_manufacturing_fit.volume_compatibility': 'WORKABLE_NOT_IDEAL',
    'addressable_btx_work.btx_relevant_component_content': 'ONE_FAMILY',
    'addressable_btx_work.repeat_volume_potential': 'SMALL_EPISODIC',
    'addressable_btx_work.cross_bu_applicability': 'ONE_BU',
    'addressable_btx_work.make_buy_propensity': 'SOURCES_EXTERNALLY',
    'program_momentum.recent_awards_funding_production_increases': 'SOME_POSITIVE',
    'program_momentum.program_linked_hiring_staffing': 'NONE',
    'program_momentum.production_delivery_milestones': 'DELAY_SLIPPAGE',
    'program_momentum.regulatory_funding_events': 'STABLE',
    'strategic_target_fit': 'STRONG_TARGET_ARCHETYPE',
    # Reconciled SAMPLE revenue now establishes one-BU commercial adjacency.
    'btx_commercial_adjacency': 'EXISTING_ONE_BU_ACTIVE',
}


def add_boeing_pursuit(account):
    """Scope one scored what-if to the existing synthetic J7 accepted revision."""
    oid = OPPORTUNITY_ID
    as_of = account['as_of']
    component_id = 'demo:j7:boeing:component'
    revision_id = 'demo:j7:boeing:revision-2'
    facility_id = 'era-elk-grove'
    role_id = oid + ':buyer-role'
    proof_id = oid + ':role-review'
    account['role_targets'].append(synthetic_record(
        role_target_id=role_id, verified_function='procurement', contact_verified=True,
        name=None, email=None, title='Authored SAMPLE procurement role, not a real Boeing person'))
    account['interactions'].append(synthetic_record(
        interaction_id=proof_id, date=as_of, real_person_ids=[], participant_role_ids=[role_id],
        related_record_ids=[oid], source_document_id='demo:j7:boeing:rfq',
        buyer_role_verified=True, meaningful_touch=False, two_way=False,
        notes='Fictional role-and-RFQ review only; no buyer conversation, introduction, or verified Boeing contact.'))
    pwin = {
        'buyer_access': {'state': 'VERIFIED_ROLE_NO_INTERACTION'},
        'competitive_position': {'state': 'ELIGIBLE_INCUMBENT'},
        'requirement_fit': {'noncritical_met': 7, 'noncritical_total': 10, 'critical_requirements_pass': True},
        'budget_process': {'state': 'CONDITIONAL_BUDGET'},
        'price_competitiveness': {'quoted_minor': 98000, 'buyer_target_minor': 100000},
        'track_record': {'state': 'CONFIRMED_NONE'},
    }
    delivery = {
        'capability_match': {'state': 'ONE_FUNDED_DATED_NONCRITICAL_GAP'},
        'schedule_feasibility': {'net_available_hours': 100, 'required_hours': 100},
        'material_readiness': {'most_constrained_critical_material_days_early': 0},
        'quality_certification': {'state': 'UNDATED_PLAN'},
        'margin': {'quoted_minor': 98000, 'estimated_total_cost_minor': 70000},
        'coordination': {'state': 'ONE_DATE_UNKNOWN'},
    }
    account['opportunities'].append(synthetic_record(
        opportunity_id=oid, component_id=component_id,
        program_id='demo:j7:boeing:program', quote_revision_id=revision_id,
        value_minor=28616000, stage='QUALIFIED', delivery_facility_id=facility_id,
        scope_requirements={
            'required_certifications': ['AS9100D'],
            'required_processes': ['5-axis milling', 'turning'],
            'required_materials': ['aluminum 7075-T6', 'titanium 6Al-4V'],
            'required_tolerance_band': 'standard aerospace (>= +/-0.001 in)',
            'expected_volume_next_12m': 240,
            'expected_hours_per_unit': 4.5,
            'required_hours_next_90d': 270,
            'required_by_date': '2027-03-31',
            'data_mode': 'SAMPLE', 'synthetic': True,
            'source': 'Authored SAMPLE scope requirements',
            'note': 'Hours figures are derived SAMPLE assumptions for classifier comparison, not buyer-stated requirements.',
        },
        title='SAMPLE J7 recovery-adjacent pursuit — not an actual Boeing opportunity',
        business_context='Authored what-if on the accepted synthetic J7 scope. The partial dispatch and unresolved inspection slot remain visible; no new award, capacity commitment, or buyer acceptance is asserted.',
        material_uncertainties=['Confirm inspection release, buyer acceptance, and any new sourcing need before execution.'],
        qualified_buyer_role_id=role_id, buyer_qualification_evidence_ids=[proof_id],
        score_observations=[authored_bin_row(
            opportunity_id=oid, path=path, bin_value=value, as_of=as_of,
            evidence_ids=(oid,), note='Authored J7 SAMPLE scoring assumption, not a verified Boeing fact.')
            for path, value in SCORE_BINS.items()],
        qualification_evidence=synthetic_record(
            opportunity_id=oid, reviewed_as_of=as_of, evidence_ids=[oid],
            identity_and_site_confirmed=True, sourced_dated_need=True,
            scoped_component_and_external_sourcing=True, no_disqualifiers=True,
            program_current=True, review_window_on=relative_date(30, anchor=as_of),
            essential_assertion_confidence=dict.fromkeys(('identity', 'need', 'capability', 'timing'), 75),
            narrative='Fictional scoped qualification exercise; no actual Boeing buyer or additional award is verified.'),
        scoring_inputs={family: {key: authored_input_row(
            opportunity_id=oid, family=family, factor=key, raw=raw,
            facility_id=facility_id, as_of=as_of,
            note='Authored SAMPLE assumption for this one pursuit; not a BTX delivery promise.')
            for key, raw in rows.items()}
            for family, rows in (('pwin', pwin), ('delivery_feasibility', delivery))},
    ))
    return account
