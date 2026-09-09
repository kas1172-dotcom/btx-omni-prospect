"""Typed record references are navigable context, never commercial/access strength."""
from calendar import monthrange
from datetime import date

from btx_omni.modules.commercial.ledger import KEYS
from btx_omni.modules.relationships.routes import RouteEdge
from btx_omni.persistence.commercial_import import digest

VERSION = 'BTX_GRAPH_RECORD_REFERENCES_1'
MODES = ('commercial_fit', 'cross_account_experience')
# Exact source fields only. An account-level quote never becomes a program-supply
# assertion; a role target never becomes a researched person's interaction.
FIELDS = {
    'rfqs': ('program_id', 'component_ids', 'requester_role_id'),
    'quotes': ('rfq_id', 'current_revision_id'),
    'quote_revisions': ('quote_id', 'supersedes_revision_id', 'line_ids'),
    'quote_lines': ('quote_revision_id', 'component_id'),
    'agreements': ('quote_id', 'accepted_revision_id', 'component_id'),
    'orders': ('quote_id', 'accepted_quote_revision_id', 'agreement_id', 'line_ids'),
    'order_lines': ('order_id', 'component_id', 'program_id', 'business_unit_id', 'btx_facility_id'),
    'cancellations': ('order_line_id',),
    'shipments': ('order_line_id',),
    'acceptances': ('shipment_id',),
    'revenue_events': ('acceptance_id', 'order_line_id'),
    'invoices': ('revenue_event_id',),
    'payments': ('invoice_id',),
    'service_events': ('related_record_ids', 'owner_role_id'),
    'interactions': ('participant_role_ids', 'related_record_ids'),
    'opportunities': ('program_id', 'quote_id', 'quote_revision_id', 'component_id', 'relationship_role_id'),
    'actions': ('case_id', 'owner_role_id', 'evidence_record_ids'),
    'fulfillment_plans': ('order_line_id',),
}
DATES = {'rfqs': 'received_date', 'quote_revisions': 'issued_date', 'agreements': 'effective_date',
         'orders': 'ordered_date', 'cancellations': 'date', 'shipments': 'shipped_date',
         'acceptances': 'accepted_date', 'revenue_events': 'recognized_date', 'invoices': 'invoice_date',
         'payments': 'paid_date', 'service_events': 'opened_date', 'interactions': 'date'}
PREDICATES = frozenset({'RECORD_BELONGS_TO_ACCOUNT'} | {'RECORD_REF_' + field.upper() for fields in FIELDS.values() for field in fields})


def project_record_references(sample, nodes, aliases):
    edges, unresolved = [], []
    for aid, account in sorted(sample.commercial_ledgers.items()):
        for collection, key in KEYS.items():
            if collection in {'programs', 'components'}:
                continue
            for record in sorted(account[collection], key=lambda item: item[key]):
                rid = record[key]
                source = aliases[rid]
                raw_date = record.get(DATES.get(collection, ''))
                observed = date.fromisoformat(raw_date) if raw_date else None
                if collection == 'monthly_commercial_history':
                    year, month = map(int, record['period'].split('-'))
                    observed = date(year, month, monthrange(year, month)[1])
                refs = [('account_id', aid)]
                for field in FIELDS.get(collection, ()):
                    values = record.get(field)
                    if isinstance(values, list):
                        refs.extend((field, value) for value in values if value)
                    elif values:
                        refs.append((field, values))
                for field, target_id in refs:
                    target = aliases.get(target_id)
                    if target is None:
                        unresolved.append({'account_id': aid, 'record_id': rid, 'field': field, 'target_id': target_id, 'reason': 'UNRESOLVED_REFERENCE'})
                        continue
                    if nodes[target].account_id not in {None, aid}:
                        raise ValueError('A record reference crosses canonical account ownership.')
                    if target == source:
                        continue
                    predicate = 'RECORD_BELONGS_TO_ACCOUNT' if field == 'account_id' else 'RECORD_REF_' + field.upper()
                    edge_id = 'record-ref:' + digest([aid, rid, field, target_id])
                    edges.append(RouteEdge(edge_id, source, target, predicate, (rid,), ('record:' + rid,),
                        ('AS-COMMERCIAL-V2',), 'POC_SCENARIO_RECORD', observed, account_id=aid,
                        component_id=record.get('component_id'), program_id=record.get('program_id'),
                        valid_from=date.fromisoformat(account['as_of']) if observed is None else None,
                        inverse_modes=MODES, derivation_rule=VERSION))
    return edges, {'version': VERSION, 'edge_count': len(edges), 'unresolved_references': unresolved,
                   'authority': 'Record references only; never route strength, program supply, personal access or available capacity.'}
