"""Shared, account-scoped canonical evidence resolution for graph and assistant."""
from btx_omni.modules.commercial.ledger import KEYS
from btx_omni.providers.research.enriched_evidence import public_sources


def evidence_supports_opportunity(ledger: dict, record_id: str, opportunity: dict) -> bool:
    """A same-account record alone cannot establish a specific pursuit input."""
    item = resolve_commercial_evidence(ledger, record_id)
    if not item:
        return False
    record = item['record']
    return (record_id == opportunity['opportunity_id']
            or record.get('opportunity_id') == opportunity['opportunity_id']
            or opportunity['opportunity_id'] in record.get('related_record_ids', [])
            or (record.get('component_id') == opportunity.get('component_id')
                and record.get('quote_revision_id') == opportunity.get('quote_revision_id')
                and bool(opportunity.get('quote_revision_id'))))


def resolve_commercial_evidence(ledger: dict, record_id: str) -> dict | None:
    for key in ('relationship_profile', 'bu_revenue_exposure'):
        record = ledger.get(key, {})
        if record.get('record_id') == record_id and record.get('provenance'):
            return {'kind': key, 'record_id': record_id, 'record': record, 'truth_class': record['provenance']['truth_class']}
    for collection, key in {**KEYS, "contacts": "contact_id", "supply_relationships": "relationship_id"}.items():
        for record in ledger.get(collection, []):
            if record[key] == record_id:
                return {"kind": collection, "record_id": record_id, "record": record,
                        "truth_class": "PUBLIC_CONTACT_CANDIDATE" if collection == "contacts" else "POC_ASSUMPTION" if collection in {"programs", "components", "supply_relationships"} else "ROLE_TARGET_NOT_RESEARCHED_PERSON" if collection == "role_targets" else "POC_SCENARIO_RECORD"}
    def referenced(value):
        if isinstance(value, dict):
            return record_id in value.get("source_ids", []) or value.get("source_id") == record_id or any(referenced(child) for child in value.values())
        if isinstance(value, list):
            return any(referenced(child) for child in value)
        return False

    source = public_sources().get(record_id) if referenced(ledger) else None
    if source:
        return {"kind": "public_source", "record_id": record_id, "record": source,
                "truth_class": "REVIEWED_SOURCE_METADATA_NOT_LIVE_PASSAGE"}
    return None
