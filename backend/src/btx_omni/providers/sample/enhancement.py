"""Additive authored demo inputs. No workbook import, random values or live IO."""
from btx_omni.core.clock import as_of_date, relative_date
from btx_omni.modules.commercial.ledger import KEYS, validate_commercial_account

VERSION = 'sample-enhancement-2026-09-20-v1'


def enhance_environment(base, *, anchor=None):
    """Opt-in SAMPLE view; old fixture files and all canonical IDs remain intact."""
    from dataclasses import replace

    from btx_omni.core.classification import Classification
    from btx_omni.core.clock import as_of_datetime
    from btx_omni.core.provenance import Provenance
    from btx_omni.domain.accounts import AccountRelationship, CanonicalAccount
    from btx_omni.domain.common import DataMode, EvidenceState
    from btx_omni.modules.commercial.projection import project_commercial_records
    from btx_omni.providers.sample.scoring_cases import (
        add_expansion,
        add_queue_examples,
        customer,
    )
    additions = [customer(case, anchor=anchor) for case in ('risk', 'watch', 'healthy', 'at-risk', 'critical')]
    add_expansion(additions[1], facility_id=base.btx_facilities[0].id)
    add_queue_examples(additions[0], facility_id=base.btx_facilities[0].id)
    critical_case = additions[-1]
    critical_case['service_events'][0].update(confirmed=True, issue_type='SAFETY_SHUTDOWN',
        narrative='Fictional safety-shutdown exercise, not an allegation about any real site. Execution is blocked pending verified clearance.')
    critical_case['actions'].append(synthetic_record(action_id='demo-fictional-critical:safety', title='Resolve fictional safety block',
        status='OPEN', owner_id='demo-role:safety', due_date=critical_case['as_of'], created_at=critical_case['as_of'],
        evidence_record_ids=[critical_case['service_events'][0]['service_event_id']]))
    clock = as_of_datetime(anchor)
    accounts = tuple(CanonicalAccount(a['account_id'], a['identity']['display_name'], AccountRelationship.CURRENT_CUSTOMER,
        None, ('Defense',), public_research_state='FICTIONAL_SAMPLE', provenance=Provenance(VERSION, a['account_id'], None, clock, clock,
            Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED, DataMode.SAMPLE, True)) for a in additions)
    base = replace(base, accounts=base.accounts + accounts)
    from btx_omni.providers.sample.regional import regional_environment
    base, regional = regional_environment(base, anchor=anchor)
    records = {**base.commercial_ledgers, 'boeing': boeing_recovery(anchor=anchor), **{a['account_id']: a for a in additions}, **regional}
    from btx_omni.providers.sample.expansion import add_boeing_expansion
    add_boeing_expansion(records['boeing'])
    projected = project_commercial_records(base, records, revision=VERSION)
    # Preserve shared graph identity even when a selected commercial scenario changes.
    preserve = {}
    for key in ('programs', 'component_classes', 'crm_contacts'):
        current = getattr(projected, key)
        ids = {item.id for item in current}
        preserve[key] = current + tuple(item for item in getattr(base, key) if item.id not in ids)
    return replace(projected, **preserve)


def completion_gaps(source, evidence):
    """A proposed plan or existing order cannot masquerade as completion proof."""
    kinds = {item.get('completion_kind') for item in evidence if item.get('verified') is True
             and source['action_id'] in item.get('related_record_ids', [])}
    return tuple(kind for kind in source.get('required_completion_evidence', []) if kind not in kinds)


def synthetic_record(**values):
    return {**values, 'synthetic': True, 'data_mode': 'SAMPLE',
            'provenance': {'truth_class': 'POC_SCENARIO', 'source_system': VERSION,
                           'authored_on': relative_date(), 'synthetic': True, 'data_mode': 'SAMPLE'}}


def empty_ledger(account_id, display_name, *, anchor=None):
    return {**{key: [] for key in KEYS}, 'contacts': [], 'supply_relationships': [],
            **synthetic_record(account_id=account_id, currency='USD', as_of=relative_date(anchor=anchor),
                               snapshot_observed_as_of=relative_date(anchor=anchor),
                               identity={'display_name': display_name})}


def reconcile_months(account):
    """Build exact ledger summaries from transactions, not independent demo numbers."""
    anchor = as_of_date(account['as_of'])
    for event in account['service_events']:
        event.setdefault('title', 'Synthetic service review — ' + account['identity']['display_name'])
        event.setdefault('details', event.get('narrative', 'Review the synthetic evidence.'))
        event.setdefault('related_record_ids', [event['order_line_id']] if event.get('order_line_id') else [])
    account['commercial_case'] = synthetic_record(title=account['identity']['display_name'],
        narrative='Authored SAMPLE scenario, not connected BTX transactions. Historical records and current review timestamps are distinct.',
        as_of=account['as_of'])
    opening = 0
    for offset in range(-11, 1):
        month_index = anchor.year * 12 + anchor.month - 1 + offset
        year, month = divmod(month_index, 12)
        period = f'{year:04d}-{month + 1:02d}'
        row = synthetic_record(snapshot_id=f"{account['account_id']}:snapshot:{period}", period=period,
                               observed_on=account['snapshot_observed_as_of'], opening_backlog_minor=opening)
        for collection, day, value, field in (
            ('orders', 'ordered_date', 'total_minor', 'bookings_minor'),
            ('shipments', 'shipped_date', 'value_minor', 'shipments_minor'),
            ('cancellations', 'date', 'value_minor', 'cancellations_minor'),
            ('revenue_events', 'recognized_date', 'revenue_minor', 'revenue_minor'),
            ('revenue_events', 'recognized_date', 'cost_minor', 'cost_of_revenue_minor'),
        ):
            row[field] = sum(r[value] for r in account[collection] if r[day].startswith(period))
        row['closing_backlog_minor'] = opening + row['bookings_minor'] - row['shipments_minor'] - row['cancellations_minor']
        row['business_unit_allocations'] = [synthetic_record(business_unit_id='BU-ERA', **{k: row[k] for k in ('revenue_minor', 'bookings_minor', 'shipments_minor')})]
        account['monthly_commercial_history'].append(row)
        opening = row['closing_backlog_minor']
    totals = {k: sum(r[k] for r in account['monthly_commercial_history']) for k in ('revenue_minor', 'bookings_minor', 'shipments_minor', 'cancellations_minor', 'cost_of_revenue_minor')}
    totals['gross_margin_minor'] = totals['revenue_minor'] - totals['cost_of_revenue_minor']
    totals['accounts_receivable_minor'] = sum(r['amount_minor'] for r in account['invoices']) - sum(r['amount_minor'] for r in account['payments'])
    account['ttm_summary'] = synthetic_record(**totals)


def boeing_recovery(*, anchor=None):
    """J7 user-supplied synthetic scenario; no claim about actual Boeing orders."""
    account = empty_ledger('boeing', 'Boeing — synthetic recovery scenario', anchor=anchor)
    day = lambda n=0: relative_date(n, anchor=account['as_of'])
    rid = lambda suffix: f'demo:j7:boeing:{suffix}'
    add = lambda collection, **row: account[collection].append(synthetic_record(**row))
    add('programs', program_id=rid('program'), name='Fictional recovery demonstration — not JDAM-LR',
        description='Synthetic accepted machining work with partial dispatch. No connection to a public Boeing program is asserted.')
    add('components', component_id=rid('component'), program_id=rid('program'), business_unit_id='BU-ERA',
        name='Fictional machined housing', technical_requirements={'material': 'demo aluminium', 'process': 'CNC machining'},
        rationale='Scenario-only capability match; not evidence that BTX supplies this component to Boeing.')
    add('rfqs', rfq_id=rid('rfq'), received_date=day(-2), notes='Synthetic request for 292 housings; material traceability required before release.')
    add('quotes', quote_id=rid('quote'), rfq_id=rid('rfq'), current_revision_id=rid('revision-2'), status='WON', decision_due_date=day(-1),
        notes='Revision 2 preserves price and splits dispatch. It does not grant acceptance of a later recovery proposal.')
    for number in (1, 2):
        add('quote_lines', quote_line_id=rid(f'quote-line-{number}'), quote_revision_id=rid(f'revision-{number}'),
            component_id=rid('component'), quantity=292, unit_price_minor=98000, line_total_minor=28616000,
            technical_requirements='Inspection report and lot traceability required; synthetic demonstration.')
        add('quote_revisions', quote_revision_id=rid(f'revision-{number}'), quote_id=rid('quote'), revision_number=number,
            issued_date=day(-2), supersedes_revision_id=rid('revision-1') if number == 2 else None,
            line_ids=[rid(f'quote-line-{number}')], total_minor=28616000,
            revision_reason='Split dispatch and inspection sequencing clarified; price unchanged.' if number == 2 else 'Initial synthetic scope.')
    add('orders', order_id=rid('order'), quote_id=rid('quote'), accepted_quote_revision_id=rid('revision-2'),
        agreement_id=None, ordered_date=day(-2), line_ids=[rid('order-line')], total_minor=28616000, status='PARTIALLY_SHIPPED')
    add('order_lines', order_line_id=rid('order-line'), order_id=rid('order'), component_id=rid('component'),
        program_id=rid('program'), business_unit_id='BU-ERA', quantity=292, unit_price_minor=98000, unit_cost_minor=70000,
        line_total_minor=28616000, committed_date=day(-1))
    for suffix, quantity, offset in [('first', 100, -1), ('second', 46, 0)]:
        add('shipments', shipment_id=rid(f'shipment-{suffix}'), order_line_id=rid('order-line'), quantity=quantity,
            value_minor=quantity * 98000, shipped_date=day(offset), notes='Synthetic partial dispatch; remaining quantity is not shipped.')
    add('service_events', service_event_id=rid('service'), order_line_id=rid('order-line'), opened_date=day(-1),
        status='OPEN', material=True, critical=False, repeated=False, repeated_within_90_days=False,
        narrative='Inspection sequencing delayed the second lot. Two dispatches total 146 units; another 146 remain. Operations must confirm the inspection slot before asking the buyer to accept a proposed date. No safety shutdown is alleged.')
    add('fulfillment_plans', plan_id=rid('recovery'), order_line_id=rid('order-line'), effective_date=day(),
        proposed_ship_date=day(6), buyer_accepted=False, status='PENDING', owner_id='demo-role:operations', due_date=day(1),
        dependency=rid('inspection-slot'), options=['Complete inspection and dispatch all 146 remaining units.', 'Offer two inspected lots after operations confirms capacity.'],
        narrative='Proposed only. Buyer acceptance and inspection evidence are missing; never describe the date as committed.')
    add('interactions', interaction_id=rid('inspection-slot'), date=day(), participant_role_ids=[], real_person_ids=[],
        meaningful_touch=False, two_way=False, related_record_ids=[rid('recovery')],
        notes='Internal synthetic planning note: operations is checking the inspection slot. No buyer conversation or warm introduction is invented.')
    add('actions', action_id=rid('action'), title='Resolve the 146-unit synthetic recovery', status='OPEN',
        owner_id='demo-role:operations', due_date=day(1), created_at=day(),
        evidence_record_ids=[rid('order-line'), rid('service'), rid('recovery')],
        completion_criteria='Attach inspection release and recorded buyer acceptance before completing recovery.',
        required_completion_evidence=['inspection_release', 'buyer_acceptance'], dependency=rid('inspection-slot'))
    reconcile_months(account)
    validate_commercial_account(account)
    return account
