"""J2: missing BU feed coverage is not zero bookings or a forecast."""
from btx_omni.providers.sample.enhancement import synthetic_record


def add_planning_context(records):
    account = records['demo-regional-defense']
    # Keep the reconciled transaction ledger intact. This is a separate import
    # coverage register for a missing BU monthly feed, not missing transactions.
    period = account['monthly_commercial_history'][-2]['period']
    sites = []
    for aid, site in [('demo-fictional-watch', 'demo-watch-southwest'),
                      ('demo-regional-defense', 'demo-regional-defense:site'),
                      ('demo-regional-medical-customer', 'demo-regional-medical-customer:site')]:
        ledger = records[aid]
        lines = {r['order_line_id']: r for r in ledger['order_lines']}
        revenue = {r['revenue_event_id']: r for r in ledger['revenue_events']}
        evidence = [r['invoice_id'] for r in ledger['invoices']
                    if lines[revenue[r['revenue_event_id']]['order_line_id']]['business_unit_id'] == 'BU-ERA']
        sites.append(synthetic_record(account_id=aid, site_id=site, business_unit_id='BU-ERA',
                                     evidence_ids=evidence, basis='SYNTHETIC_INVOICED_ACTIVITY'))
    account['commercial_case']['planning_context'] = synthetic_record(
        business_unit_id='BU-APM', observed_on=account['as_of'],
        monthly_history_coverage=[synthetic_record(period=period, state='UNKNOWN', value_minor=None,
            source_url='sample://fictional/bu-apm/monthly-feed-gap', publisher='Authored SAMPLE exercise',
            event_date=account['as_of'], retrieval_date=account['as_of'],
            reason='The APM monthly planning extract is absent. Individual transactions remain available; do not infer zero, a target shortfall or a forecast.')],
        sister_business_unit_sites=sites,
        next_step='Recover the absent monthly planning extract and reconcile it to the existing transaction ledger before setting a target.',
        forecast=None, target=None,
        what_would_change_result='A dated, reconciled BU planning extract resolves the coverage gap; it does not establish future demand.')


def planning_view(view, environment):
    """Read-only defaults. A persisted false designation overrides the fixture."""
    records = list(view['partnership_records'])
    known = {r['account_id'] for r in records}
    contexts = []
    for aid, ledger in sorted(environment.commercial_ledgers.items()):
        site = ledger.get('site_context', {})
        if site.get('strategic_partnership') and aid not in known:
            records.append(synthetic_record(account_id=aid, designated=True,
                reason='Fictional SAMPLE strategic partnership; not a real BTX designation.',
                version=None, updated_by='demo-role:planning', updated_at=ledger['as_of']))
        context = ledger.get('commercial_case', {}).get('planning_context')
        if context:
            contexts.append({'account_id': aid, **context})
    return {**view, 'partnership_records': records,
            'strategic_partnerships': [r for r in records if r.get('designated', True)],
            'business_unit_history': contexts}
