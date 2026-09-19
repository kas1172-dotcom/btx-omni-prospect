"""Shared pursuit projection for the workspace, account links and Omni."""
from btx_omni.modules.scoring.commercial_decisions import opportunity_decisions


def account_opportunities(sample, account_id: str) -> list[dict]:
    account = next((a for a in sample.accounts if a.id == account_id), None)
    ledger = sample.commercial_ledgers.get(account_id)
    if account is None or ledger is None:
        return []
    lane = ("CUSTOMER_EXPANSION" if account.relationship.value in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"}
            else "PROSPECT" if account.relationship.value in {"TARGET", "PROSPECT"} else "REVIEW_REQUIRED")
    records = {r['opportunity_id']: r for r in ledger['opportunities']}
    components = {r['component_id']: r for r in ledger.get('components', [])}
    results = []
    for decision in opportunity_decisions(ledger, account_id=account_id, revision=sample.commercial_revision,
                                         facility_ids=frozenset(f.id for f in sample.btx_facilities)):
        record = records[decision['opportunity_id']]
        component = components.get(decision['component_id'], {})
        actions = sorted((a for a in ledger.get('actions', []) if decision['opportunity_id'] in a.get('evidence_record_ids', [])), key=lambda a: a['action_id'])
        results.append({**decision, 'account_name': account.legal_name, 'lane': lane,
                        'title': record.get('title') or component.get('name') or 'Component pursuit',
                        'next_action': actions[0]['title'] if actions else None,
                        'business_context': record.get('business_context'),
                        'material_uncertainties': record.get('material_uncertainties', [record['blocking_question']] if record.get('blocking_question') else []),
                        'source_record_id': decision['opportunity_id'], 'as_of': ledger['as_of'],
                        'revision': sample.commercial_revision})
    return results


def selected_opportunity(sample, selection: dict) -> dict:
    if selection.get('revision') != sample.commercial_revision:
        raise ValueError('Selected opportunity has changed; reopen it before continuing.')
    row = next((r for r in account_opportunities(sample, selection.get('account_id'))
                if r['opportunity_id'] == selection.get('opportunity_id')), None)
    if row is None:
        raise ValueError('Selected opportunity is not available in this organization.')
    return row
