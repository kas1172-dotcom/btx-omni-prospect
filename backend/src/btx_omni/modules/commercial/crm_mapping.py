"""Retain exact existing account-scoped CRM ownership; never infer a new owner."""
import json
from hashlib import sha256


def retained_crm_mapping(companies, account_id):
    matches = [company for company in companies if company.account_id == account_id]
    if len(matches) > 1:
        raise ValueError('Ambiguous existing CRM account mapping requires review.')
    if not matches:
        return None, {'owner_status': 'UNRESOLVED_ROLE', 'owner_mapping_version': 'BTX_CRM_MAPPING_1'}
    company = matches[0]
    if (company.properties or {}).get('owner_mapping_version') == 'BTX_CRM_MAPPING_1':
        return company.owner_id, dict(company.properties)
    provenance = company.provenance
    return company.owner_id, {
        'owner_mapping_version': 'BTX_CRM_MAPPING_1',
        'owner_status': 'RETAINED_EXISTING_OWNER' if company.owner_id else 'UNRESOLVED_ROLE',
        'source_company_id': company.id,
        'owner_provenance': {'source_system': provenance.source_system, 'source_record_id': provenance.source_record_id,
                             # The legacy loader fills missing source dates with
                             # load time. That is not evidence of assignment age.
                             'observed_at': None, 'recorded_at': None, 'date_status': 'SOURCE_ASSIGNMENT_DATE_UNAVAILABLE',
                             'assignment_hash': sha256(json.dumps([provenance.source_system, company.id, company.owner_id]).encode()).hexdigest(),
                             'synthetic': provenance.synthetic, 'data_mode': provenance.data_mode.value},
        'authority': 'Existing scenario CRM assignment, not a researched public person or a verified live HubSpot mapping.',
    }
