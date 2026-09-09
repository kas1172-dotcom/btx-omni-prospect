"""Project persisted scenario records into the existing shared commercial model.

No public events or personal introductions are inferred here. Source-shaped
records remain available for deeper, lossless evidence retrieval.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    AccountRelationship,
    PublicContactResearch,
    ResearchProvenance,
)
from btx_omni.domain.commercial import CommercialContext, MonthlyCommercialHistory
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.crm import CrmActivity, CrmCompany, CrmDeal
from btx_omni.domain.orders import Order
from btx_omni.domain.programs import ComponentClass, Program
from btx_omni.domain.quotes import (
    CommercialQuote,
    CommercialQuoteLineItem,
    PaperlessAccount,
    QuoteStatus,
)
from btx_omni.modules.commercial.crm_mapping import retained_crm_mapping
from btx_omni.modules.scoring.commercial_inputs import commercial_attractiveness_inputs
from btx_omni.persistence.commercial_import import BU_CROSSWALK, PACKAGE_KEY
from btx_omni.providers.research.enriched_evidence import public_sources
from btx_omni.providers.sample.environment import SampleEnvironment


def project_commercial_records(
    base: SampleEnvironment, records: dict[str, dict], *, revision: str, crm_mappings: dict | None = None,
) -> SampleEnvironment:
    targeted = set(records)
    scoring = {aid: commercial_attractiveness_inputs(account) for aid, account in records.items()}
    source_catalog = public_sources()
    contact_projections: dict[str, tuple] = {}
    if not targeted <= {a.id for a in base.accounts}:
        raise ValueError("Persisted commercial account is outside the canonical catalog")
    output: dict[str, list] = {key: [] for key in (
        "commercial_contexts", "paperless_accounts", "quotes", "orders", "programs",
        "component_classes", "crm_companies", "crm_deals", "crm_activities",
    )}
    for aid, account in sorted(records.items()):
        observed = datetime.fromisoformat(account["as_of"]).replace(tzinfo=UTC)
        contacts = []
        for contact in account["contacts"]:
            sources = [source_catalog[sid] for sid in contact["source_ids"]]
            contacts.append(PublicContactResearch(
                "PUBLIC_CONTACT_CANDIDATE", contact["role_scope"], contact["employment_status"],
                sources[0]["source_type"] if sources else None,
                sources[0]["url"] if sources else None,
                ResearchProvenance(tuple(contact["source_ids"]), tuple(s["url"] for s in sources), contact["employment_status"], datetime.fromisoformat(contact["observed_on"]).replace(tzinfo=UTC)),
                name=contact["full_name"], title_or_function=contact["title_as_published"],
                public_email=contact.get("email"),
            ))
        contact_projections[aid] = tuple(contacts)

        def provenance(rid, record=None, *, inferred=False, observed=observed):
            authored = (record or {}).get("provenance", {}).get("authored_on")
            recorded = datetime.fromisoformat(authored).replace(tzinfo=UTC) if authored else observed
            return Provenance(
                PACKAGE_KEY, rid, None, observed, recorded,
                Classification.INTERNAL_COMMERCIAL,
                EvidenceState.INFERRED if inferred else EvidenceState.CONFIRMED,
                DataMode.SAMPLE, True,
            )

        components = {r["component_id"]: r for r in account["components"]}
        order_lines = {r["order_line_id"]: r for r in account["order_lines"]}
        quote_lines = {r["quote_line_id"]: r for r in account["quote_lines"]}
        revisions = {r["quote_revision_id"]: r for r in account["quote_revisions"]}
        bu_ids = sorted({r["business_unit_id"] for r in components.values()})
        crm_id, paperless_id = f"crm:{aid}", f"paperless:{aid}"
        if crm_mappings is not None:
            mapping = crm_mappings.get(aid)
            if mapping is None or mapping['id'] != crm_id:
                raise ValueError('Persisted CRM mapping is missing from its canonical account scope.')
            crm_owner, crm_properties = mapping['owner_id'], mapping['properties']
        else:
            crm_owner, crm_properties = retained_crm_mapping(base.crm_companies, aid)
        output["crm_companies"].append(CrmCompany(crm_id, aid, crm_owner, provenance(crm_id), properties=crm_properties))
        output["paperless_accounts"].append(PaperlessAccount(paperless_id, aid, account["identity"]["display_name"], provenance(paperless_id)))
        for bu in bu_ids:
            monthly = []
            for month in sorted(account["monthly_commercial_history"], key=lambda r: r["period"]):
                allocation = next((r for r in month["business_unit_allocations"] if r["business_unit_id"] == bu), None)
                monthly.append(MonthlyCommercialHistory(
                    date.fromisoformat(month["period"] + "-01"),
                    allocation["revenue_minor"] if allocation else None,
                    allocation["bookings_minor"] if allocation else None,
                    provenance(month["snapshot_id"], month),
                ))
            def total(field, monthly=monthly):
                values = [getattr(m, field) for m in monthly]
                return sum(values) if all(v is not None for v in values) else None
            dates = [date.fromisoformat(order["ordered_date"]) for order in account["orders"] if any(order_lines[lid]["business_unit_id"] == bu for lid in order["line_ids"])]
            latest = max(dates, default=None)
            output["commercial_contexts"].append(CommercialContext(
                aid, BU_CROSSWALK[bu], account["currency"], total("revenue_minor"), total("bookings_minor"),
                None, None, None, None, latest, latest, tuple(monthly),
                provenance(f"commercial:{aid}:{bu}"),
                last_crm_activity_date=max((date.fromisoformat(r["date"]) for r in account["interactions"]), default=None),
            ))
        for program in account["programs"]:
            output["programs"].append(Program(program["program_id"], aid, program["name"], None, EvidenceState.INFERRED, provenance(program["program_id"], program, inferred=True)))
        for component in components.values():
            output["component_classes"].append(ComponentClass(component["component_id"], component["program_id"], component["name"], EvidenceState.INFERRED, provenance(component["component_id"], component, inferred=True), business_unit_ids=(BU_CROSSWALK[component["business_unit_id"]],)))
        for quote in account["quotes"]:
            rev = revisions[quote["current_revision_id"]]
            lines = [quote_lines[lid] for lid in rev["line_ids"]]
            units = {BU_CROSSWALK[components[line["component_id"]]["business_unit_id"]] for line in lines}
            programs = {components[line["component_id"]]["program_id"] for line in lines}
            output["quotes"].append(CommercialQuote(
                quote["quote_id"], aid, next(iter(units)) if len(units) == 1 else "MULTIPLE_BUSINESS_UNITS",
                QuoteStatus(quote["status"]), date.fromisoformat(rev["issued_date"]), rev["total_minor"], account["currency"], None, None, None,
                provenance(quote["quote_id"], quote),
                program_id=next(iter(programs)) if len(programs) == 1 else None,
                component_class_ids=tuple(sorted({line["component_id"] for line in lines})), paperless_account_id=paperless_id,
                business_unit_ids=tuple(sorted(units)),
                line_items=tuple(CommercialQuoteLineItem(line["quote_line_id"], components[line["component_id"]].get("technical_requirements", {}).get("actual_customer_part_number"), line["component_id"], line["quantity"], line["unit_price_minor"], None, provenance(line["quote_line_id"], line)) for line in lines),
            ))
        for order in account["orders"]:
            for lid in order["line_ids"]:
                line = order_lines[lid]
                shipments = [r for r in account["shipments"] if r["order_line_id"] == lid]
                # A partial shipment is not completion. Acceptance/revenue is
                # retrieved separately, never inferred from this projection.
                shipped = sum(r["quantity"] for r in shipments)
                completed = max((date.fromisoformat(r["shipped_date"]) for r in shipments), default=None) if shipped == line["quantity"] else None
                output["orders"].append(Order(
                    order["order_id"] if len(order["line_ids"]) == 1 else lid,
                    order["quote_id"], aid, BU_CROSSWALK[line["business_unit_id"]],
                    components[line["component_id"]].get("technical_requirements", {}).get("actual_customer_part_number"),
                    line["component_id"], line["program_id"], None, None,
                    date.fromisoformat(line["committed_date"]) if line.get("committed_date") else None,
                    completed, order["status"], line["quantity"], line["line_total_minor"], provenance(lid, line), parent_order_id=order["order_id"],
                ))
        for interaction in account["interactions"]:
            output["crm_activities"].append(CrmActivity(interaction["interaction_id"], crm_id, datetime.fromisoformat(interaction["date"]).replace(tzinfo=UTC), provenance(interaction["interaction_id"], interaction), aid, interaction))
        for opportunity in account["opportunities"]:
            output["crm_deals"].append(CrmDeal(opportunity["opportunity_id"], crm_id, BU_CROSSWALK[components[opportunity["component_id"]]["business_unit_id"]], provenance(opportunity["opportunity_id"], opportunity), aid, opportunity["program_id"], opportunity))

    old_programs = {p.id for p in base.programs if p.account_id in targeted}
    old_companies = {c.id for c in base.crm_companies if c.account_id in targeted}
    old_components = {c.id for c in base.component_classes if c.program_id in old_programs}
    # Other customers may legitimately reference a shared public program or
    # component. Replacing one account's scenario cannot remove their catalog.
    retained_component_ids = {o.component_class_id for o in base.orders if o.account_id not in targeted}
    retained_component_ids.update(cid for q in base.quotes if q.account_id not in targeted for cid in q.component_class_ids)
    retained_program_ids = {q.program_id for q in base.quotes if q.account_id not in targeted and q.program_id}
    retained_program_ids.update(o.program_id for o in base.orders if o.account_id not in targeted)
    retained_program_ids.update(c.program_id for c in base.component_classes if c.id in retained_component_ids and c.program_id)
    old_programs -= retained_program_ids
    old_components -= retained_component_ids
    for field, additions in output.items():
        def retained(item, field=field):
            if field == "component_classes":
                return item.id not in old_components
            if field == "programs":
                return item.id not in old_programs
            if field == "paperless_accounts":
                return item.canonical_account_id not in targeted
            return getattr(item, "account_id", None) not in targeted
        output[field] = tuple(item for item in getattr(base, field) if retained(item)) + tuple(additions)
    return replace(
        base, **output,
        accounts=tuple(replace(a, relationship=AccountRelationship.CURRENT_CUSTOMER if records[a.id]["ttm_summary"]["revenue_minor"] > 0 else a.relationship, business_units=tuple(sorted({BU_CROSSWALK[c["business_unit_id"]] for c in records[a.id]["components"]})), public_contacts=contact_projections[a.id]) if a.id in targeted else a for a in base.accounts),
        crm_contacts=tuple(c for c in base.crm_contacts if c.company_id not in old_companies),
        rich_scenarios={k: v for k, v in base.rich_scenarios.items() if k not in targeted},
        priority_scenarios={k: v for k, v in base.priority_scenarios.items() if k not in targeted},
        matching_components=tuple(c for c in base.matching_components if c.id not in old_components and c.account_id not in targeted),
        matching_quotes=tuple(q for q in base.matching_quotes if q.account_id not in targeted),
        scoring_inputs={**base.scoring_inputs, **{aid: dict(value.selections) for aid, value in scoring.items()}},
        scoring_evidence={**base.scoring_evidence, **{aid: dict(value.evidence_by_factor) for aid, value in scoring.items()}},
        commercial_ledgers=records, commercial_revision=revision,
    )
