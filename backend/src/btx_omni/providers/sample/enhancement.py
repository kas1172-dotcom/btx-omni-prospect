"""Additive authored demo inputs. No workbook import, random values or live IO."""
from datetime import date, timedelta

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
    from btx_omni.providers.sample.pursuit_cases import add_pursuit_cases
    add_pursuit_cases(additions[1])
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
    add_boeing_financials(records['boeing'])
    from btx_omni.providers.sample.expansion import add_boeing_expansion
    add_boeing_expansion(records['boeing'])
    from btx_omni.providers.sample.named_company_cases import add_named_company_cases
    base = add_named_company_cases(base, records, anchor=anchor)
    from btx_omni.providers.sample.relationship_cases import prepare_relationships
    prepare_relationships(records)
    from btx_omni.providers.sample.planning_cases import add_planning_context
    add_planning_context(records)
    from btx_omni.providers.sample.rubric_examples import examples
    records['demo-fictional-watch']['commercial_case']['rubric_examples'] = examples(anchor=anchor)
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
        lines = {r['order_line_id']: r for r in account['order_lines']}
        orders = {r['order_id']: r for r in account['orders']}
        row['business_unit_allocations'] = []
        for bu in sorted({r['business_unit_id'] for r in account['components']}):
            row['business_unit_allocations'].append(synthetic_record(business_unit_id=bu,
                bookings_minor=sum(r['line_total_minor'] for r in lines.values() if r['business_unit_id'] == bu and orders[r['order_id']]['ordered_date'].startswith(period)),
                revenue_minor=sum(r['revenue_minor'] for r in account['revenue_events'] if lines[r['order_line_id']]['business_unit_id'] == bu and r['recognized_date'].startswith(period)),
                shipments_minor=sum(r['value_minor'] for r in account['shipments'] if lines[r['order_line_id']]['business_unit_id'] == bu and r['shipped_date'].startswith(period))))
        account['monthly_commercial_history'].append(row)
        opening = row['closing_backlog_minor']
    totals = {k: sum(r[k] for r in account['monthly_commercial_history']) for k in ('revenue_minor', 'bookings_minor', 'shipments_minor', 'cancellations_minor', 'cost_of_revenue_minor')}
    totals['gross_margin_minor'] = totals['revenue_minor'] - totals['cost_of_revenue_minor']
    totals['accounts_receivable_minor'] = sum(r['amount_minor'] for r in account['invoices']) - sum(r['amount_minor'] for r in account['payments'])
    account['ttm_summary'] = synthetic_record(**totals)


def add_boeing_financials(account):
    """Simulated historical releases; keep J7's unaccepted recovery line separate."""
    as_of = date.fromisoformat(account['as_of'])
    first_index = as_of.year * 12 + as_of.month - 12
    # One booked release per month through August; the existing J7 order is
    # September's booked release. Four older releases ship in three monthly lots.
    order_quantities = (180, 185, 190, 195, 200, 210, 220, 225, 230, 220, 230)
    unit_price, unit_cost = 100000, 70000

    def month_day(index, day):
        year, month = divmod(first_index + index, 12)
        return date(year, month + 1, day)

    def add(collection, **row):
        account[collection].append(synthetic_record(
            **row, source='Authored SAMPLE commercial record'))

    for index, quantity in enumerate(order_quantities):
        prefix = f'sample:boeing:release:{index + 1:02d}'
        received, issued, ordered = (month_day(index, day).isoformat() for day in (3, 4, 5))
        quote_id, revision_id, quote_line_id = (f'{prefix}:{part}' for part in ('quote', 'revision', 'quote-line'))
        order_id, order_line_id = f'{prefix}:order', f'{prefix}:order-line'
        value = quantity * unit_price
        add('rfqs', rfq_id=f'{prefix}:rfq', received_date=received,
            notes='Synthetic recurring housing release; no actual Boeing request.')
        add('quotes', quote_id=quote_id, rfq_id=f'{prefix}:rfq', current_revision_id=revision_id,
            status='WON', decision_due_date=ordered)
        add('quote_lines', quote_line_id=quote_line_id, quote_revision_id=revision_id,
            component_id='demo:j7:boeing:component', quantity=quantity,
            unit_price_minor=unit_price, line_total_minor=value,
            technical_requirements='Synthetic recurring housing lot; not a buyer drawing.')
        add('quote_revisions', quote_revision_id=revision_id, quote_id=quote_id,
            revision_number=1, issued_date=issued, supersedes_revision_id=None,
            line_ids=[quote_line_id], total_minor=value)
        fulfilled = index in (0, 3, 6, 9)
        superseded = index in (1, 2, 4)
        add('orders', order_id=order_id, quote_id=quote_id,
            accepted_quote_revision_id=revision_id, agreement_id=None,
            ordered_date=ordered, line_ids=[order_line_id], total_minor=value,
            status='FULFILLED' if fulfilled else 'CANCELLED' if superseded else 'OPEN')
        add('order_lines', order_line_id=order_line_id, order_id=order_id,
            component_id='demo:j7:boeing:component', program_id='demo:j7:boeing:program',
            business_unit_id='BU-ERA', quantity=quantity, unit_price_minor=unit_price,
            unit_cost_minor=unit_cost, line_total_minor=value,
            committed_date=(month_day(index + 2, 20) if fulfilled else as_of + timedelta(days=180)).isoformat())
        if superseded:
            add('cancellations', cancellation_id=f'{prefix}:cancellation', order_line_id=order_line_id,
                quantity=quantity, value_minor=value, date=month_day(index, 20).isoformat(),
                narrative='Superseded SAMPLE release; gross booking and reversal remain separately visible.')

    for index in range(12):
        source_index = index // 3 * 3
        ordered = order_quantities[source_index]
        lot = ordered // 3 if index % 3 < 2 else ordered - 2 * (ordered // 3)
        prefix = f'sample:boeing:release:{source_index + 1:02d}'
        line_id = f'{prefix}:order-line'
        shipment_id = f'sample:boeing:dispatch:{index + 1:02d}'
        shipped = month_day(index, 10)
        invoice_date = shipped
        due = invoice_date + timedelta(days=30)
        paid = due + timedelta(days=6) if index == 0 else due if index == 1 else min(due - timedelta(days=10), as_of)
        amount = lot * unit_price
        add('shipments', shipment_id=shipment_id, order_line_id=line_id,
            quantity=lot, value_minor=amount, shipped_date=shipped.isoformat())
        acceptance_id = f'{shipment_id}:acceptance'
        revenue_id = f'{shipment_id}:revenue'
        invoice_id = f'{shipment_id}:invoice'
        add('acceptances', acceptance_id=acceptance_id, shipment_id=shipment_id,
            accepted_date=shipped.isoformat(), quantity=lot)
        add('revenue_events', revenue_event_id=revenue_id, acceptance_id=acceptance_id,
            order_line_id=line_id, recognized_date=shipped.isoformat(), quantity=lot,
            revenue_minor=amount, cost_minor=lot * unit_cost)
        add('invoices', invoice_id=invoice_id, revenue_event_id=revenue_id,
            invoice_date=invoice_date.isoformat(), due_date=due.isoformat(), amount_minor=amount)
        add('payments', payment_id=f'{shipment_id}:payment', invoice_id=invoice_id,
            paid_date=paid.isoformat(), amount_minor=amount)

    # Current fictional agreement is documented demand continuity, not a
    # representation of a real Boeing contract or a public-program award.
    agreement_id = 'sample:boeing:release:01:agreement'
    add('agreements', agreement_id=agreement_id,
        accepted_revision_id='sample:boeing:release:01:revision',
        effective_date=month_day(0, 5).isoformat(),
        end_date=(as_of + timedelta(days=365)).isoformat())
    next(order for order in account['orders']
         if order['order_id'] == 'sample:boeing:release:01:order')['agreement_id'] = agreement_id

    for months_ago, material in ((4, True), (8, False)):
        event_date = month_day(11 - months_ago, 12).isoformat()
        add('service_events', service_event_id=f'boeing:sample-service:{months_ago}m',
            opened_date=event_date, updated_date=event_date, status='RESOLVED',
            material=material, critical=False, repeated=False, repeated_within_90_days=False,
            narrative='Resolved noncritical SAMPLE documentation issue; not an actual Boeing service event.')

    role_ids = ('boeing:sample-role:procurement', 'boeing:sample-role:engineering')
    for role_id, function in zip(role_ids, ('procurement', 'engineering'), strict=True):
        add('role_targets', role_target_id=role_id, verified_function=function,
            contact_verified=True, name=None, email=None,
            narrative='Synthetic function-level role; no real person or contact is asserted.')
    add('interactions', interaction_id='boeing:sample-touch:review',
        date=(as_of - timedelta(days=15)).isoformat(), participant_role_ids=list(role_ids),
        real_person_ids=[], meaningful_touch=True, two_way=True, related_record_ids=[],
        notes='Simulated two-function account review, not an actual Boeing conversation.')
    account['relationship_profile'] = synthetic_record(
        record_id='boeing:relationship-profile:sample', relationship_started_on='2019-04-15',
        expected_touch_days=30, contact_review_complete=True,
        interaction_review_complete=True, risk_history_review_complete=True,
        quote_review_complete=True, service_review_complete=True,
        payment_review_complete=True, current_demand_evidence_ids=[agreement_id],
        source='Authored SAMPLE relationship profile')

    account['monthly_commercial_history'] = []
    reconcile_months(account)
    for month in account['monthly_commercial_history']:
        month['source'] = 'Authored SAMPLE commercial record; reconciled from simulated transactions'
        for allocation in month['business_unit_allocations']:
            allocation['source'] = month['source']
    account['ttm_summary']['source'] = 'Authored SAMPLE commercial record; reconciled from simulated transactions'
    revenue = account['ttm_summary']['revenue_minor']
    account['bu_revenue_exposure'] = synthetic_record(
        record_id='boeing:bu-revenue-exposure:sample', business_unit_id='BU-ERA',
        period_start=account['monthly_commercial_history'][0]['period'] + '-01',
        period_end=account['as_of'], account_revenue_minor=revenue,
        bu_revenue_minor=revenue * 8,
        source='Authored SAMPLE commercial record; BU denominator is simulated, not BTX financials')
    validate_commercial_account(account)
    return account


def boeing_recovery(*, anchor=None):
    """J7 user-supplied synthetic scenario; no claim about actual Boeing orders."""
    account = empty_ledger('boeing', 'Boeing — synthetic recovery scenario', anchor=anchor)
    day = lambda n=0: relative_date(n, anchor=account['as_of'])
    rid = lambda suffix: f'demo:j7:boeing:{suffix}'
    add = lambda collection, **row: account[collection].append(synthetic_record(**row))
    add('programs', program_id=rid('program'), name='Fictional recovery demonstration — not JDAM-LR',
        expected_production_horizon_years=3, source='Authored SAMPLE program-horizon assumption',
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
