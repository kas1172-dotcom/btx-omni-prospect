"""Read-only Profiles fields composed from the existing canonical services.

No scoring policy lives here. Unknown values stay null; SAMPLE role contacts
are not represented as identified people or externally verified relationships.
"""
from datetime import date

from btx_omni.modules.accounts.customer_360 import customer_360_projection
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.modules.scoring.customer_health import health_inputs
from btx_omni.modules.scoring.families import assess, customer_risk_projection
from btx_omni.modules.scoring.internal_risk import risk_inputs


def profile_projection(sample, account, *, alerts, signal_briefs, monitoring_complete):
    snapshot = CommercialReadService(sample).account_snapshot(account.id)
    canonical = customer_360_projection(account_id=account.id, sample=sample,
                                        commercial=snapshot, signals=[])
    ledger = sample.commercial_ledgers.get(account.id)
    customer = account.relationship.value in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"}
    state = fulfillment_state(ledger, canonical_account_id=account.id,
                              revision=sample.commercial_revision) if ledger else None
    health = health_inputs(ledger, state) if ledger else {}
    risk = risk_inputs(ledger, state) if ledger else {}
    internal = assess("internal_commercial_risk", subject_id=account.id,
                      as_of=ledger['as_of'] if ledger else '', revision=sample.commercial_revision,
                      inputs=risk, eligible=customer and bool(ledger))
    public = customer_risk_projection(account_id=account.id, current_customer=customer,
        internal_decision=internal, signal_briefs=signal_briefs,
        monitoring_complete=monitoring_complete)
    active = {event['underlying_event_id']: event for event in public['public_risk_events'] if event['active']}
    internal_items = {item.id: item for item in alerts if item.account_id == account.id and item.status == 'OPEN'}
    months = sorted((row for row in (ledger or {}).get('monthly_commercial_history', [])
                     if row['period'] <= ledger['as_of'][:7]), key=lambda row: row['period'])[-12:]
    def raw(inputs, key):
        value = inputs.get(key)
        return value.raw_value if value else None
    fields = {
        'owner_id': canonical['crm']['owner_id'],
        'business_unit_ids': [row['id'] for row in canonical['business_units']],
        'naics': (ledger or {}).get('naics_assignments', []),
        # The existing health rubric defines points, not bands. Never substitute
        # confidence/risk thresholds or a frontend-invented health threshold.
        'health_band': None,
        'health_band_state': 'NOT_CONFIGURED' if customer else 'NOT_APPLICABLE',
        'open_items': {'public': len(active), 'internal': len(internal_items)},
        'bookings_monthly': [{'period': row['period'], 'bookings_minor': row['bookings_minor'],
                              'currency': row.get('currency', ledger['currency']), 'snapshot_id': row['snapshot_id'],
                              'provenance': row.get('provenance')} for row in months],
        'bookings_delta_3m_vs_prior_3m': raw(health, 'commercial_trajectory'),
        'last_activity_at': canonical['crm']['last_activity_at'],
    }
    coverage = []
    roles = (ledger or {}).get('role_targets', [])
    interactions = (ledger or {}).get('interactions', [])
    # Case-only labels are the same function, not a second missing contact.
    function_labels = {label.casefold(): label for label in account.contact_role_families or ()}
    function_labels.update({role['verified_function'].casefold(): role['verified_function']
                            for role in roles if role.get('verified_function')})
    functions = sorted(function_labels.values())
    for function in functions:
        matching = [role for role in roles if str(role.get('verified_function', '')).casefold() == function.casefold()]
        verified = [role for role in matching if role.get('contact_verified') is True]
        ids = {role['role_target_id'] for role in verified}
        touches = [row for row in interactions if row.get('two_way') is True
                   and ids.intersection(row.get('participant_role_ids', []))
                   and row.get('date') and row['date'] <= ledger['as_of']]
        last = max((row['date'] for row in touches), default=None)
        recent = bool(last and 0 <= (date.fromisoformat(ledger['as_of']) - date.fromisoformat(last)).days <= 90)
        coverage.append({'function': function, 'state': 'Present' if verified and recent else 'Thin' if verified else 'Unknown',
                         'role_ids': sorted(ids), 'last_two_way_at': last,
                         'verification_scope': sorted({role.get('verification_scope', 'Unknown') for role in verified}),
                         'source_state': 'SAMPLE' if matching else 'UNAVAILABLE'})
    lines = (state or {}).get('lines', [])
    prices = {row['order_line_id']: row['unit_price_minor'] for row in (ledger or {}).get('order_lines', [])}
    return {**fields,
        'backlog_months': raw(health, 'backlog_coverage'),
        'quote_overdue_share': raw(risk, 'pipeline'),
        'concentration': {'share': raw(risk, 'concentration'), 'evidence': (ledger or {}).get('bu_revenue_exposure')},
        'open_order_count': len({row['order_id'] for row in lines if row['remaining_quantity'] > 0}) if state else None,
        'open_order_value_minor': sum(row['remaining_quantity'] * prices[row['order_line_id']] for row in lines) if state else None,
        'fulfillment': state,
        'function_coverage': coverage,
        'last_two_way_at': max((row['date'] for row in interactions if row.get('two_way') is True
                                and row.get('date') and row['date'] <= ledger['as_of']), default=None),
        'expected_touch_days': (ledger or {}).get('relationship_profile', {}).get('expected_touch_days'),
        'internal_commercial_risk': internal if ledger and customer else None,
        'public_risk_rollup': public['public_risk_rollup'],
        'public_risk_events': list(active.values()),
        'overall_customer_risk': public['overall_customer_risk'],
        'open_internal_items': list(internal_items.values()),
        'expansion_opportunity_count': len((ledger or {}).get('opportunities', [])) if customer and ledger else None,
    }


LIST_PROFILE_FIELDS = ('owner_id', 'business_unit_ids', 'naics', 'health_band', 'health_band_state',
                       'open_items', 'bookings_monthly', 'bookings_delta_3m_vs_prior_3m', 'last_activity_at')
