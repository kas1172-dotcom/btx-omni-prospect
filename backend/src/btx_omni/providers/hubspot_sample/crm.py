from __future__ import annotations

from datetime import datetime

from btx_omni.core.classification import Classification
from btx_omni.domain.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_crm(*, account_ids: set[str], business_unit_ids: set[str], program_ids: set[str]) -> tuple[tuple[CrmCompany, ...], tuple[CrmContact, ...], tuple[CrmDeal, ...], tuple[CrmActivity, ...]]:
    payload = document("btx_sample_hubspot_crm.json")
    companies = []
    for row in payload["companies"]:
        if row["research_account_id"] not in account_ids: raise ValueError("CRM company references unknown account")
        companies.append(CrmCompany(row["hs_object_id"], row["research_account_id"], row["properties"].get("hubspot_owner_id"), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL), row["properties"].get("name"), row["properties"]))
    company_ids = {item.id for item in companies}
    contacts, deals, activities = [], [], []
    for row in payload["contacts"]:
        if row["research_account_id"] not in account_ids or row["associated_hs_company_id"] not in company_ids: raise ValueError("CRM contact has unknown foreign key")
        contacts.append(CrmContact(row["hs_object_id"], row["associated_hs_company_id"], row["properties"].get("btx_role_family_console_enriched", "unknown"), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL), row["research_account_id"], row["properties"]))
    for row in payload["deals"]:
        props = row["properties"]
        if row["research_account_id"] not in account_ids or row["associated_hs_company_id"] not in company_ids or props.get("btx_business_unit_console_enriched") not in business_unit_ids or props.get("btx_program_id_console_enriched") not in program_ids: raise ValueError("CRM deal has unknown foreign key")
        deals.append(CrmDeal(row["hs_object_id"], row["associated_hs_company_id"], props.get("btx_business_unit_console_enriched"), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL), row["research_account_id"], props.get("btx_program_id_console_enriched"), props))
    for row in payload["activities"]:
        if row["research_account_id"] not in account_ids or row["associated_hs_company_id"] not in company_ids: raise ValueError("CRM activity has unknown foreign key")
        activities.append(CrmActivity(row["hs_object_id"], row["associated_hs_company_id"], datetime.fromisoformat(row["properties"]["hs_engagement_timestamp"]), source_provenance(row, classification=Classification.INTERNAL_COMMERCIAL), row["research_account_id"], row["properties"]))
    return tuple(companies), tuple(contacts), tuple(deals), tuple(activities)
