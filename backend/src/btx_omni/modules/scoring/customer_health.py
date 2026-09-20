"""Rubric v2 section 10: health is not the inverse of commercial risk."""
from datetime import date, timedelta
from decimal import Decimal

from btx_omni.modules.scoring.families import FactorInput


def health_inputs(account: dict, fulfillment: dict) -> dict[str, FactorInput]:
    as_of = date.fromisoformat(account['as_of'])
    cutoff = as_of - timedelta(days=365)
    months = sorted((r for r in account['monthly_commercial_history'] if r['period'] <= as_of.strftime('%Y-%m')), key=lambda r: r['period'])
    result = {}

    def put(key, points, evidence, reason, raw=None):
        result[key] = FactorInput(Decimal(points) if points is not None else None,
            tuple(sorted(set(evidence))), reason, raw_value=raw, period=account['as_of'])

    def contiguous(rows, count):
        nums = [int(r['period'][:4]) * 12 + int(r['period'][5:7]) for r in rows]
        return len(nums) == count and nums == list(range(nums[0], nums[0] + count))

    recent = sum(r['bookings_minor'] for r in months[-3:])
    previous = sum(r['bookings_minor'] for r in months[-6:-3])
    change = Decimal(recent - previous) / previous if contiguous(months[-6:], 6) and previous > 0 else None
    points = None if change is None else 100 if change >= Decimal('.10') else 75 if change >= 0 else 50 if change > Decimal('-.10') else 25 if change >= Decimal('-.25') else 0
    put('commercial_trajectory', points, [r['snapshot_id'] for r in months[-6:]], 'Latest three months of bookings versus the preceding three. A missing or zero comparison baseline is not assumed growth.', str(change) if change is not None else None)

    profile = account.get('relationship_profile', {})
    ids = (profile['record_id'],) if profile.get('record_id') and profile.get('provenance') else ()
    interactions = [r for r in account['interactions'] if r.get('date') and cutoff <= date.fromisoformat(r['date']) <= as_of]
    roles = {r['role_target_id']: r for r in account['role_targets'] if r.get('verified_function') and r.get('contact_verified') is True}
    active = [r for r in interactions if r.get('two_way') is True and (as_of - date.fromisoformat(r['date'])).days <= 90]
    functions = {roles[rid]['verified_function'] for r in active for rid in r.get('participant_role_ids', []) if rid in roles}
    complete = bool(ids) and profile.get('contact_review_complete') is True
    points = (100 if len(functions) >= 3 else 75 if len(functions) == 2 else 50 if functions else 25 if roles else 0) if complete else None
    put('relationship_coverage', points, [*ids, *roles, *(r['interaction_id'] for r in active)], 'Distinct verified functions with two-way engagement in 90 days. Unverified role targets do not establish engagement.', len(functions) if complete else None)

    last = max((r for r in interactions if r.get('meaningful_touch') is True), key=lambda r: r['date'], default=None)
    cadence = profile.get('expected_touch_days')
    reviewed = bool(ids) and profile.get('interaction_review_complete') is True
    ratio = Decimal((as_of - date.fromisoformat(last['date'])).days) / Decimal(str(cadence)) if last and isinstance(cadence, int) and cadence > 0 and reviewed else None
    points = (100 if ratio <= 1 else 75 if ratio <= Decimal('1.5') else 50 if ratio <= 2 else 25 if ratio <= 3 else 0) if ratio is not None else 0 if reviewed and not last else None
    put('engagement_cadence', points, [*ids, *([last['interaction_id']] if last else [])], 'Meaningful touch recency compared with the documented expected cadence; generic notes are not automatically meaningful touches.', str(ratio) if ratio is not None else None)

    lines = {r['order_line_id']: r for r in account['order_lines']}
    backlog = sum(r['remaining_quantity'] * lines[r['order_line_id']]['unit_price_minor'] for r in fulfillment['lines'])
    revenue = sum(r['revenue_minor'] for r in months[-12:])
    coverage = Decimal(backlog) * 12 / revenue if contiguous(months[-12:], 12) and revenue > 0 else None
    points = None if coverage is None else 100 if coverage >= 6 else 75 if coverage >= 3 else 50 if coverage >= 1 else 25 if coverage > 0 else 0
    put('backlog_coverage', points, [*(r['snapshot_id'] for r in months[-12:]), *lines], 'Committed remaining order value divided by average monthly revenue over twelve consecutive recorded months.', str(coverage) if coverage is not None else None)

    started = date.fromisoformat(profile['relationship_started_on']) if ids and profile.get('relationship_started_on') else None
    fulfilled = [r for r in account['orders'] if r.get('status') == 'FULFILLED' and cutoff <= date.fromisoformat(r['ordered_date']) <= as_of]
    years = as_of.year - started.year - ((as_of.month, as_of.day) < (started.month, started.day)) if started else None
    history = None if years is None or years < 0 else 0 if profile.get('terminated') is True else 100 if years >= 5 and len(fulfilled) >= 2 else 75 if years >= 2 and len(fulfilled) >= 2 else 50 if years >= 1 and fulfilled else 25
    put('relationship_history', history, [*ids, *(r['order_id'] for r in fulfilled)], 'Documented relationship start and fulfilled orders; the sample file start is not assumed to be the relationship start.')

    cases = [r for r in account['service_events'] if cutoff <= date.fromisoformat(r['opened_date']) <= as_of and r.get('material') is True]
    unresolved = [r for r in cases if r.get('status') not in {'RESOLVED', 'CLOSED'}]
    reviewed = bool(ids) and profile.get('risk_history_review_complete') is True and all('material' in r for r in account['service_events'])
    risk = None
    if reviewed and all('critical' in r for r in unresolved) and all('repeated_within_90_days' in r for r in cases):
        risk = 0 if any(r['critical'] for r in unresolved) else 25 if len(unresolved) >= 2 else 50 if unresolved else 100 if not cases else 75 if not any(r['repeated_within_90_days'] for r in cases) else None
    put('attached_risk_history', risk, [*ids, *(r['service_event_id'] for r in cases)], 'Material case history is independent of invoice aging. Unreviewed severity or recurrence is not assumed clear.')
    return result
