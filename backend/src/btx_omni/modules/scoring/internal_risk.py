"""Rubric v2 internal risk; unknown evidence is not a healthy observation."""
from datetime import date
from decimal import Decimal

from btx_omni.modules.scoring.customer_health import health_inputs
from btx_omni.modules.scoring.families import FactorInput


def risk_inputs(account: dict, fulfillment: dict) -> dict[str, FactorInput]:
    health = health_inputs(account, fulfillment)
    result = {}
    as_of = date.fromisoformat(account['as_of'])
    profile = account.get('relationship_profile', {})
    policy_ids = (profile['record_id'],) if profile.get('record_id') and profile.get('provenance') else ()

    def put(key, points, evidence, reason, raw=None):
        result[key] = FactorInput(Decimal(points) if points is not None else None,
            tuple(sorted(set(evidence))), reason, raw_value=raw, period=account['as_of'])

    trajectory = health['commercial_trajectory']
    change = Decimal(trajectory.raw_value) if trajectory.raw_value is not None else None
    points = None if change is None else 100 if change < Decimal('-.25') else 75 if change <= Decimal('-.10') else 50 if change < 0 else 25 if change < Decimal('.10') else 0
    put('commercial_momentum', points, trajectory.evidence_ids, trajectory.reason, trajectory.raw_value)

    revisions = {r['quote_revision_id']: r for r in account['quote_revisions']}
    open_quotes = [q for q in account['quotes'] if q.get('status') == 'OPEN']
    complete = bool(policy_ids) and profile.get('quote_review_complete') is True
    complete = complete and all(q.get('current_revision_id') in revisions and (q.get('decision_due_date') or q.get('decision_date')) for q in open_quotes)
    total = sum(revisions[q['current_revision_id']]['total_minor'] for q in open_quotes if q.get('current_revision_id') in revisions)
    overdue = sum(revisions[q['current_revision_id']]['total_minor'] for q in open_quotes if q.get('current_revision_id') in revisions and (q.get('decision_due_date') or q.get('decision_date')) and date.fromisoformat(q.get('decision_due_date') or q['decision_date']) < as_of)
    share = Decimal(overdue) / total if complete and total > 0 else None
    points = None if share is None else 100 if share > Decimal('.50') else 75 if share >= Decimal('.25') else 50 if share >= Decimal('.10') else 25 if share > 0 else 0
    # An empty pipeline is not automatically healthy: a current agreement or
    # recent RFQ must be explicitly linked and reviewed.
    continuity = [r['agreement_id'] for r in account['agreements']
        if r['agreement_id'] in profile.get('current_demand_evidence_ids', [])
        and r.get('effective_date') and r.get('end_date') and r['effective_date'] <= account['as_of'] <= r['end_date']]
    if share == 0 and not continuity:
        points = None
    if complete and not open_quotes and continuity:
        points = 0
    put('pipeline', points, [*policy_ids, *(q['quote_id'] for q in open_quotes), *continuity],
        'Past-due open quote value as a share of all open quote value. Closed-quote win rate is not this factor.', str(share) if share is not None else None)

    backlog = health['backlog_coverage']
    months = Decimal(backlog.raw_value) if backlog.raw_value is not None else None
    points = None if months is None else 100 if months == 0 else 75 if months < 1 else 50 if months < 3 else 25 if months < 6 else 0
    put('backlog', points, backlog.evidence_ids, backlog.reason, backlog.raw_value)

    coverage = health['relationship_coverage']
    count = coverage.raw_value
    verified = any(r.get('contact_verified') is True and r.get('verified_function') for r in account['role_targets'])
    points = None if count is None else 0 if count >= 3 else 25 if count == 2 else 50 if count == 1 else 75 if verified else 100
    put('engagement', points, coverage.evidence_ids, coverage.reason, count)

    concentration = account.get('bu_revenue_exposure', {})
    exposure_ids = (concentration['record_id'],) if concentration.get('record_id') and concentration.get('provenance') else ()
    numerator, denominator = concentration.get('account_revenue_minor'), concentration.get('bu_revenue_minor')
    valid = bool(exposure_ids) and bool(concentration.get('business_unit_id')) and concentration.get('period_end') == account['as_of'] and concentration.get('period_start')
    valid = valid and isinstance(numerator, int) and isinstance(denominator, int) and 0 <= numerator <= denominator and denominator > 0
    share = Decimal(numerator) / denominator if valid else None
    points = None if share is None else 100 if share > Decimal('.35') else 75 if share >= Decimal('.20') else 50 if share >= Decimal('.10') else 25 if share > Decimal('.05') else 0
    put('concentration', points, exposure_ids, 'Account revenue as a share of the relevant BTX business unit revenue over the same documented period; not concentration within the customer’s programs.', str(share) if share is not None else None)

    cases = [r for r in account['service_events'] if date.fromisoformat(r['opened_date']) <= as_of and r.get('status') not in {'RESOLVED', 'CLOSED'}]
    reviewed = bool(policy_ids) and profile.get('service_review_complete') is True and profile.get('payment_review_complete') is True
    known = reviewed and all(isinstance(r.get('critical'), bool) and isinstance(r.get('repeated'), bool) for r in cases)
    payments = {}
    for payment in account['payments']:
        if date.fromisoformat(payment['paid_date']) <= as_of:
            payments[payment['invoice_id']] = payments.get(payment['invoice_id'], 0) + payment['amount_minor']
    invoices = [r for r in account['invoices'] if date.fromisoformat(r['invoice_date']) <= as_of and r['amount_minor'] > payments.get(r['invoice_id'], 0)]
    known = known and all(r.get('due_date') for r in invoices)
    late_days = max([0, *((as_of - date.fromisoformat(r['due_date'])).days for r in invoices if r.get('due_date'))])
    points = None
    if known:
        points = 100 if any(r['critical'] for r in cases) or late_days >= 60 else 75 if late_days >= 31 else 50 if any(r['repeated'] for r in cases) or late_days >= 16 else 25 if cases or late_days > 0 else 0
    put('friction', points, [*policy_ids, *(r['service_event_id'] for r in cases), *(r['invoice_id'] for r in invoices)],
        'Worst documented open service issue or overdue-payment age. A small overdue balance can still require attention.', late_days if known else None)
    return result
