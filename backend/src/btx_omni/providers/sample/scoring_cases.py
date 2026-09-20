"""Fictional commercial customers with reconciled leaf inputs for v2 examples."""
from datetime import date

from btx_omni.core.clock import as_of_date, relative_date
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.providers.sample.enhancement import empty_ledger, reconcile_months, synthetic_record

EXPANSION_BINS = {
    'program_durability.expected_production_horizon': 'FIVE_TO_NINE_YEARS',
    'program_durability.repeat_production_pattern': 'MULTIPLE_BATCHES_NOT_LOCKED',
    'program_durability.commitment_strength': 'BUDGETED_CREDIBLE_FUNDING',
    'program_durability.industry_specific_maturity_evidence': 'STRONG_EVIDENCE',
    'btx_manufacturing_fit.material_match': 'ROUTINE',
    'btx_manufacturing_fit.process_tolerance_match': 'EDGE_BUT_ANALOGOUS',
    'btx_manufacturing_fit.certification_compliance_fit': 'MINOR_GAP',
    'btx_manufacturing_fit.volume_compatibility': 'WORKABLE_NOT_IDEAL',
    'addressable_btx_work.btx_relevant_component_content': 'LIMITED_SET',
    'addressable_btx_work.repeat_volume_potential': 'LARGE_RECURRING',
    'addressable_btx_work.cross_bu_applicability': 'TWO_PLUS_BU',
    'addressable_btx_work.make_buy_propensity': 'SOURCES_EXTERNALLY',
    'program_momentum.recent_awards_funding_production_increases': 'CLEAR_POSITIVE_RECENT',
    'program_momentum.program_linked_hiring_staffing': 'VISIBLE_SURGE',
    'program_momentum.production_delivery_milestones': 'SCALE_UP_OR_MAJOR',
    'program_momentum.regulatory_funding_events': 'MATERIALLY_HURTS',
    'strategic_target_fit': 'CORE_TARGET_ARCHETYPE',
    'btx_commercial_adjacency': 'EXISTING_ONE_BU_ACTIVE',
}


def customer(case='risk', *, anchor=None):
    identity = f'demo-fictional-{case}'
    account = empty_ledger(identity, f'Fictional {case.title()} Manufacturing — SAMPLE', anchor=anchor)
    anchor_date = as_of_date(account['as_of'])
    day = lambda n=0: relative_date(n, anchor=anchor_date)
    rid = lambda key: f'{identity}:{key}'
    def add(collection, **row):
        item = synthetic_record(**row)
        account[collection].append(item)
        return item
    add('programs', program_id=rid('program'), name='Fictional multi-year precision platform',
        description='Entirely fictional five-to-nine-year production program with budgeted batches and more than 24 months of accepted historical production. Not a real public award.')
    add('components', component_id=rid('component'), program_id=rid('program'), business_unit_id='BU-ERA',
        name='Fictional precision housing family', technical_requirements={'material': 'scenario aluminium', 'process': 'machining'},
        rationale='Synthetic scoped component for the example; no real buyer, sourcing need or capability claim.')
    # Twelve months of actual scenario transactions. Observation dates are current;
    # historical transaction dates are deliberately retained for longitudinal scores.
    base = 145000 if case == 'risk' else 100000
    recent = 118900 if case == 'risk' else 95000
    if case == 'healthy':
        recent = 115000
    elif case in {'at-risk', 'critical'}:
        recent = 60000
    total_shipments = 1375200 if case == 'risk' else 948000
    if case in {'at-risk', 'critical'}:
        total_shipments = 1000000
    other_shipment = (total_shipments - 2 * base) // 10
    for index in range(12):
        month_index = anchor_date.year * 12 + anchor_date.month - 1 - 11 + index
        year, month = divmod(month_index, 12)
        occurred = day(-2) if index == 11 else date(year, month + 1, 15).isoformat()
        qty = base if index < 9 else recent
        # Late low-booking months use earlier backlog via separate lines? Avoid
        # cross-line over-shipment: retain a lower dispatched quantity in those cases.
        shipped = min(qty, base if index < 2 else other_shipment)
        qid, rev, qline, oid, line = (rid(f'{key}-{index}') for key in ('quote', 'revision', 'quote-line', 'order', 'order-line'))
        add('rfqs', rfq_id=rid(f'rfq-{index}'), received_date=occurred, narrative='Synthetic recurring lot request; historical transaction, refreshed in current snapshot.')
        add('quotes', quote_id=qid, rfq_id=rid(f'rfq-{index}'), current_revision_id=rev, status='WON', decision_due_date=occurred)
        add('quote_revisions', quote_revision_id=rev, quote_id=qid, revision_number=1, issued_date=occurred,
            supersedes_revision_id=None, line_ids=[qline], total_minor=qty * 100, revision_reason='Synthetic accepted release; unchanged unit price.')
        add('quote_lines', quote_line_id=qline, quote_revision_id=rev, component_id=rid('component'), quantity=qty,
            unit_price_minor=100, line_total_minor=qty * 100, technical_requirements='Scenario drawing revision A; all critical checks separately reviewed.')
        add('orders', order_id=oid, quote_id=qid, accepted_quote_revision_id=rev, agreement_id=None, ordered_date=occurred,
            line_ids=[line], total_minor=qty * 100, status='FULFILLED' if shipped == qty else 'PARTIALLY_SHIPPED')
        add('order_lines', order_line_id=line, order_id=oid, component_id=rid('component'), program_id=rid('program'),
            business_unit_id='BU-ERA', quantity=qty, unit_price_minor=100, unit_cost_minor=70,
            line_total_minor=qty * 100, committed_date=day(30))
        add('shipments', shipment_id=rid(f'ship-{index}'), order_line_id=line, shipped_date=occurred, quantity=shipped, value_minor=shipped * 100)
        add('acceptances', acceptance_id=rid(f'accept-{index}'), shipment_id=rid(f'ship-{index}'), accepted_date=occurred, quantity=shipped)
        add('revenue_events', revenue_event_id=rid(f'revenue-{index}'), acceptance_id=rid(f'accept-{index}'), order_line_id=line,
            recognized_date=occurred, quantity=shipped, revenue_minor=shipped * 100, cost_minor=shipped * 70)
        add('invoices', invoice_id=rid(f'invoice-{index}'), revenue_event_id=rid(f'revenue-{index}'), invoice_date=occurred,
            due_date=day(20), amount_minor=shipped * 100)
        add('payments', payment_id=rid(f'payment-{index}'), invoice_id=rid(f'invoice-{index}'), paid_date=occurred, amount_minor=shipped * 100)
    for name, value, due in [('overdue', 15000, -1), ('current', 85000, 10)]:
        add('rfqs', rfq_id=rid(name+'-rfq'), received_date=day(-2), notes='Synthetic open quote supporting value-weighted aging.')
        add('quotes', quote_id=rid(name+'-quote'), rfq_id=rid(name+'-rfq'), status='OPEN', current_revision_id=rid(name+'-revision'), decision_due_date=day(due))
        add('quote_revisions', quote_revision_id=rid(name+'-revision'), quote_id=rid(name+'-quote'), revision_number=1, issued_date=day(-2),
            supersedes_revision_id=None, line_ids=[rid(name+'-line')], total_minor=value)
        add('quote_lines', quote_line_id=rid(name+'-line'), quote_revision_id=rid(name+'-revision'), component_id=rid('component'),
            quantity=1, unit_price_minor=value, line_total_minor=value, technical_requirements='Fictional scoped manufacturing requirement.')
    count = 3 if case == 'healthy' else 0 if case in {'at-risk', 'critical'} else 1
    for index in range(count):
        add('role_targets', role_target_id=rid(f'function-{index}'), verified_function=('procurement', 'engineering', 'operations')[index],
            contact_verified=True, name=None, email=None, narrative='Synthetic function-level engagement only; no named person or introduction.')
    add('interactions', interaction_id=rid('touch'), date=day(-1 if case in {'risk', 'healthy'} else -60 if case == 'watch' else -30 if case == 'at-risk' else -120),
        two_way=True, meaningful_touch=True, participant_role_ids=[r['role_target_id'] for r in account['role_targets']], real_person_ids=[],
        related_record_ids=[], notes='Synthetic function-level review: price held; decision process and delivery assumptions require confirmation. No real conversation is asserted.')
    account['relationship_profile'] = synthetic_record(record_id=rid('relationship-policy'), relationship_started_on=day(-365 * 7),
        expected_touch_days=30, contact_review_complete=True, interaction_review_complete=True, risk_history_review_complete=True,
        quote_review_complete=True, service_review_complete=True, payment_review_complete=True, current_demand_evidence_ids=[])
    if case != 'healthy':
        add('service_events', service_event_id=rid('service'), opened_date=day(-1), status='RESOLVED' if case == 'watch' else 'OPEN',
            material=True, critical=case == 'critical', repeated=False, repeated_within_90_days=False,
            narrative='Fictional documentation discrepancy, resolved with a review checklist.' if case == 'watch' else 'Fictional service case requires inspection reconciliation; no real customer allegation.')
    reconcile_months(account)
    account['bu_revenue_exposure'] = synthetic_record(record_id=rid('exposure'), business_unit_id='BU-ERA', period_start=account['monthly_commercial_history'][0]['period']+'-01',
        period_end=day(), account_revenue_minor=account['ttm_summary']['revenue_minor'], bu_revenue_minor=account['ttm_summary']['revenue_minor'] * 14)
    validate_commercial_account(account)
    return account


def add_expansion(account, *, facility_id):
    oid = account['account_id'] + ':expansion'
    line = account['quote_lines'][-1]
    facts = [synthetic_record(opportunity_id=oid, path=key, bin=value, reviewed_as_of=account['as_of'],
                             evidence_ids=[oid], narrative='Fictional scoped rubric input; not public research.') for key, value in EXPANSION_BINS.items()]
    account['opportunities'].append(synthetic_record(opportunity_id=oid, component_id=line['component_id'],
        program_id=account['programs'][0]['program_id'], quote_revision_id=line['quote_revision_id'],
        value_minor=25000000, stage='QUALIFIED', delivery_facility_id=facility_id, score_observations=facts,
        title='Fictional five-to-nine-year housing expansion',
        business_context='Budgeted repeat batches; analogous process needs adaptation and a dated nonmandatory certification remedy. One component has potential cross-BU process steps. Scenario-only regulatory headwind offsets strong program momentum.',
        material_uncertainties=['Confirm the adaptation trial and the dated remedy before committing production.'],
        qualification_evidence=synthetic_record(opportunity_id=oid, reviewed_as_of=account['as_of'], evidence_ids=[oid],
            identity_and_site_confirmed=True, sourced_dated_need=True, scoped_component_and_external_sourcing=True,
            no_disqualifiers=True, program_current=True, review_window_on=relative_date(30, anchor=account['as_of']),
            essential_assertion_confidence=dict.fromkeys(('identity', 'need', 'capability', 'timing'), 75))))
    return account


def add_queue_examples(account, *, facility_id):
    """Same-customer escalation, fully assessed RFQ, and lower-priority cooling work."""
    from btx_omni.modules.scoring.public_inputs import public_risk_assessment
    from btx_omni.core.clock import as_of_datetime
    from btx_omni.providers.sample.risk_cases import risk_context
    add_expansion(account, facility_id=facility_id)
    opportunity = account['opportunities'][-1]
    overrides = {
        'program_durability.repeat_production_pattern': 'ESTABLISHED_RECURRING',
        'program_durability.commitment_strength': 'FUNDED_AWARDED_CONTRACTED',
        'btx_manufacturing_fit.process_tolerance_match': 'ROUTINE',
        'btx_manufacturing_fit.certification_compliance_fit': 'ALL_MET',
        'btx_manufacturing_fit.volume_compatibility': 'NORMAL_RANGE',
        'addressable_btx_work.btx_relevant_component_content': 'MULTIPLE_FAMILIES',
        'addressable_btx_work.cross_bu_applicability': 'ONE_BU',
        'program_momentum.recent_awards_funding_production_increases': 'SOME_POSITIVE',
        'program_momentum.regulatory_funding_events': 'MATERIALLY_IMPROVES',
    }
    for row in opportunity['score_observations']:
        row['bin'] = overrides.get(row['path'], row['bin'])
    opportunity['business_context'] = 'Fictional funded recurring multi-family RFQ with routine manufacturing fit. No actual buyer commitment is asserted.'
    event, observation = risk_context(anchor=account['as_of'])
    risk = public_risk_assessment(event, observation, now=as_of_datetime(account['as_of']))
    account['public_event_assessments'] = {event.id: risk}
    account['interactions'].append(synthetic_record(interaction_id=event.id, date=account['as_of'], real_person_ids=[], participant_role_ids=[],
        notes='Fictional filing exercise reviewed for action triage; do not present as an SEC disclosure.', related_record_ids=[]))
    for key, title, evidence, owner, event_id in [
        ('escalate', 'Review fictional consolidation risk', event.id, 'demo-role:account-owner', event.id),
        ('rfq', 'Validate fictional expansion RFQ', opportunity['opportunity_id'], 'demo-role:seller', None),
        ('cooling', 'Re-engage fictional cooling customer', account['service_events'][0]['service_event_id'], None, None),
    ]:
        account['actions'].append(synthetic_record(action_id=account['account_id'] + ':' + key, title=title,
            status='OPEN', owner_id=owner, due_date=relative_date(1, anchor=account['as_of']), created_at=account['as_of'],
            evidence_record_ids=[evidence], underlying_event_id=event_id,
            completion_criteria='Record the review outcome and next accountable owner; this is synthetic seller work.'))
    return account
