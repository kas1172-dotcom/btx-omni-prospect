"""Synthetic manufacturing routes only. No people or warm introductions."""
from copy import deepcopy

from btx_omni.providers.sample.enhancement import reconcile_months, synthetic_record


def prepare_relationships(records):
    for account in records.values():
        for program in account['programs']:
            program.setdefault('source_ids', [program['program_id']])
        for component in account['components']:
            component.setdefault('source_ids', [component['component_id']])
            component.setdefault('btx_facility_id', 'BTX-FAC-BU-APM' if component['business_unit_id'] == 'BU-APM' else 'BTX-FAC-BU-ERA')
        components = {r['component_id']: r for r in account['components']}
        for line in account['order_lines']:
            line.setdefault('btx_facility_id', components[line['component_id']]['btx_facility_id'])
    account = records['demo-regional-defense']
    cid = account['components'][0]['component_id']
    second = deepcopy(account['components'][0])
    second.update(component_id=cid + ':inspection', name='Fictional legacy inspection component', business_unit_id='BU-APM',
                  btx_facility_id='BTX-FAC-BU-APM', source_ids=[cid + ':inspection'])
    account['components'].append(second)
    # Two older accepted orders establish weaker freshness than the current route.
    early = {r['order_id'] for r in account['orders'][:2]}
    for row in account['order_lines']:
        if row['order_id'] in early:
            row.update(component_id=second['component_id'], business_unit_id='BU-APM', btx_facility_id='BTX-FAC-BU-APM')
    for row in account['quote_lines'][:2]:
        row['component_id'] = second['component_id']
    rid = account['account_id'] + ':joint-inspection-review'
    account['interactions'].append(synthetic_record(interaction_id=rid, date=account['as_of'], real_person_ids=[], participant_role_ids=[],
        related_record_ids=[r['order_id'] for r in account['orders'][-2:]], two_way=False, meaningful_touch=False,
        notes='Fictional manufacturing-record review: ERA machining followed by APM inspection coordination. Not a person-to-person access route or a reserved capacity slot.'))
    account['route_evidence'] = [synthetic_record(id=rid, source_facility_id='era-elk-grove', target_facility_id='apm-rochester',
        component_id=cid, evidence_ids=[rid], accepted_order_ids=[r['order_id'] for r in account['orders'][-2:]],
        observed_on=account['as_of'], source_url='sample://fictional/' + rid,
        publisher='Authored manufacturing exercise', event_date=account['as_of'], retrieval_date=account['as_of'],
        narrative='Synthetic machining-to-inspection handoff record, not personal access. Validate actual capability and capacity before execution.')]
    account['unsupported_route_links'] = [synthetic_record(from_id=account['account_id'], to_id='boeing',
        state='HYPOTHESIZED_UNSUPPORTED', reason='No evidence connects this fictional organization to Boeing or JDAM-LR.', source_url=None)]
    account['monthly_commercial_history'] = []
    reconcile_months(account)
    return records
