"""Bounded, canonical Customer 360 read projection.

This projection deliberately composes provider-neutral records at the backend
boundary.  It never resolves a Customer by name and it preserves source-state
truth rather than turning an absent provider record into a zero value.
"""
from __future__ import annotations

from typing import Any

from btx_omni.modules.commercial.read import CommercialAccountSnapshot
from btx_omni.providers.sample.environment import SampleEnvironment


def organization_360_projection(*, account, commercial: CommercialAccountSnapshot, signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Project one governed organization mode without asking the UI or a model to classify it."""
    relationship = account.relationship.value
    has_commercial_history = bool(
        commercial.commercial_context
        or commercial.quotes
        or commercial.orders
    )
    confirmed_customer = relationship in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"}
    contradictory = has_commercial_history and not confirmed_customer
    if contradictory:
        mode = "RELATIONSHIP_REVIEW"
        title = "Relationship needs review"
        rationale = "Canonical commercial records exist, but the governed organization classification does not confirm a customer relationship."
    elif confirmed_customer:
        mode = "CUSTOMER"
        title = "Customer 360"
        rationale = "The canonical account classification confirms a current or former BTX customer relationship."
    elif relationship in {"PROSPECT", "TARGET", "PUBLIC_MARKET"}:
        mode = "PROSPECT"
        title = "Prospect 360"
        rationale = "No confirmed BTX commercial relationship is present in the governed account classification."
    else:
        mode = "RELATIONSHIP_REVIEW"
        title = "Relationship needs review"
        rationale = "The governed relationship classification is unresolved."

    assessments = [
        item.get("business_briefing")
        for item in signals
        if isinstance(item.get("business_briefing"), dict)
    ]
    expansion = next(
        (
            item
            for item in assessments
            if confirmed_customer
            and item.get("analysis_status") == "READY"
            and item.get("commercial_relevance_state")
            in {
                "REVIEW_REQUIRED",
                "ESTABLISHED_ACCOUNT_REVIEW",
                "ESTABLISHED_COMMERCIAL_RELEVANCE",
            }
            and (
                item.get("technical_opportunity")
                or (item.get("evidence_package") or {}).get("technical_decomposition")
            )
        ),
        None,
    )
    return {
        "mode": mode,
        "title": title,
        "relationship_label": (
            "Confirmed BTX customer"
            if confirmed_customer
            else "Relationship needs review"
            if mode == "RELATIONSHIP_REVIEW"
            else "No confirmed BTX commercial relationship"
        ),
        "classification_basis": rationale,
        "classification_source": {
            "owner": "canonical_account.relationship",
            "source_system": getattr(account.provenance, "source_system", None),
            "source_record_id": getattr(account.provenance, "source_record_id", None),
        },
        "has_commercial_history": has_commercial_history,
        "expansion_pursuit": (
            {
                "assessment_id": expansion.get("assessment_id"),
                "assessment_version": expansion.get("assessment_version"),
                "event_id": expansion.get("id"),
                "headline": expansion.get("headline"),
                "program_id": expansion.get("canonical_program_id"),
                "governed_action": expansion.get("recommended_action"),
            }
            if expansion
            else None
        ),
    }


def _provenance(item: object) -> dict[str, Any]:
    provenance = getattr(item, "provenance", None)
    if provenance is None:
        return {"source_system": "UNAVAILABLE", "source_record_id": None, "data_mode": "UNAVAILABLE", "evidence_state": "UNAVAILABLE"}
    return {
        "source_system": provenance.source_system,
        "source_record_id": provenance.source_record_id,
        "source_url": provenance.source_url,
        "data_mode": provenance.data_mode,
        "evidence_state": provenance.evidence_state,
    }


def customer_360_projection(*, account_id: str, sample: SampleEnvironment, commercial: CommercialAccountSnapshot, signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stable, bounded sections for one already-resolved canonical id."""
    contexts = sorted(commercial.commercial_context, key=lambda item: item.business_unit)
    quotes = sorted(commercial.quotes, key=lambda item: (item.quoted_at, item.id), reverse=True)[:10]
    orders = sorted(commercial.orders, key=lambda item: (item.actual_ship_date or item.promised_date or item.id, item.id), reverse=True)[:10]
    programs = sorted((item for item in sample.programs if item.account_id == account_id), key=lambda item: (item.name, item.id))[:10]
    program_ids = {item.id for item in programs}
    # A quote/deal can provide a governed program relation even where the program
    # record was loaded from a different canonical catalog slice.
    program_ids.update(item.program_id for item in quotes if item.program_id)
    program_ids.update(item.program_id for item in commercial.crm["deals"] if item.program_id)
    programs_by_id = {item.id: item for item in sample.programs if item.id in program_ids}
    component_ids = {
        component_id
        for quote in quotes
        for component_id in (*quote.component_class_ids, *(line.component_class_id for line in quote.line_items))
    }
    components = sorted(
        (item for item in sample.component_classes if item.program_id in program_ids or item.id in component_ids),
        key=lambda item: (item.name, item.id),
    )[:20]
    bu_ids = {bu for component in components for bu in component.business_unit_ids}
    bu_ids.update(item.business_unit for item in quotes)
    bu_ids.update(item.business_unit for item in contexts)
    capabilities = sorted((item for item in sample.capabilities if set(item.business_units) & bu_ids), key=lambda item: (item.name, item.id))[:20]
    business_units = {item.id: item for item in sample.business_units}
    facilities = sorted((item for item in sample.facilities if item.account_id == account_id), key=lambda item: (item.name, item.id))[:10]

    commercial_rows = [
        {
            "business_unit_id": item.business_unit,
            "business_unit": business_units.get(item.business_unit).name if item.business_unit in business_units else item.business_unit,
            "currency": item.currency,
            "ttm_revenue_minor": item.ttm_revenue_minor,
            "ttm_bookings_minor": item.ttm_bookings_minor,
            "last_booking_date": item.last_booking_date,
            "last_order_date": item.last_order_date,
            "provenance": _provenance(item),
        }
        for item in contexts
    ]
    quote_rows = [
        {"id": item.id, "status": item.status, "quoted_at": item.quoted_at, "value_minor": item.value_minor,
         "currency": item.currency, "program_id": item.program_id, "business_unit_id": item.business_unit,
         "business_unit": business_units.get(item.business_unit).name if item.business_unit in business_units else item.business_unit,
         "component_class_ids": item.component_class_ids, "provenance": _provenance(item)}
        for item in quotes
    ]
    order_rows = [
        {"id": item.id, "status": item.status, "amount_minor": item.amount_minor, "program_id": item.program_id,
         "component_class_id": item.component_class_id, "business_unit_id": item.business_unit_id,
         "business_unit": business_units.get(item.business_unit_id).name if item.business_unit_id in business_units else item.business_unit_id,
         "recent_order_date": item.actual_ship_date or item.promised_date, "provenance": _provenance(item)}
        for item in orders
    ]
    crm_contacts = sorted(commercial.crm["contacts"], key=lambda item: item.id)[:10]
    crm_rows = [{"id": item.id, "role_family": item.role_family, "name": (item.properties or {}).get("firstname") or (item.properties or {}).get("name"),
                 "title": (item.properties or {}).get("jobtitle"), "provenance": _provenance(item)} for item in crm_contacts]
    return {
        "commercial": {"source_state": commercial.source_states["commercial"], "records": commercial_rows,
                       "missing": "No linked commercial history" if not commercial_rows else None},
        "quotes": {"source_state": commercial.source_states["paperless"], "records": quote_rows,
                   "missing": "No linked quote history" if not quote_rows else None},
        "orders": {"source_state": commercial.source_states["orders"], "records": order_rows,
                   "missing": "No linked order history" if not order_rows else None},
        "crm": {"source_state": commercial.source_states["crm"], "owner_id": next((item.owner_id for item in commercial.crm["companies"] if item.owner_id), None),
                "contacts": crm_rows, "deal_count": len(commercial.crm["deals"]), "activity_count": len(commercial.crm["activities"]),
                "last_activity_at": max((item.occurred_at for item in commercial.crm["activities"]), default=None),
                "missing": "No linked CRM context" if not commercial.crm["companies"] else None},
        "programs": [{"id": item.id, "name": item.name, "system": item.system, "evidence_state": item.evidence_state, "provenance": _provenance(item)} for item in sorted(programs_by_id.values(), key=lambda item: (item.name, item.id))[:10]],
        "components": [{"id": item.id, "program_id": item.program_id, "name": item.name, "business_unit_ids": item.business_unit_ids, "evidence_state": item.evidence_state, "provenance": _provenance(item)} for item in components],
        "capabilities": [{"id": item.id, "name": item.name, "description": item.description, "business_unit_ids": item.business_units, "provenance": _provenance(item)} for item in capabilities],
        "business_units": [{"id": item.id, "name": item.name} for item in sorted((business_units[item] for item in bu_ids if item in business_units), key=lambda item: item.name)],
        "facilities": [{"id": item.id, "name": item.name, "city": item.city, "region": item.region, "country": item.country, "facility_type": item.facility_type, "verification_state": item.verification_state, "source_url": item.source_url} for item in facilities],
        "intelligence": sorted(signals, key=lambda item: (str(item.get("observed_at", "")), str(item.get("id", ""))), reverse=True)[:10],
        "missingness": {
            "programs": "No canonical program relation" if not programs_by_id else None,
            "capabilities": "No governed component or capability relation" if not components and not capabilities else None,
            "facilities": "No canonical facility linked" if not facilities else None,
            "intelligence": "No recent intelligence" if not signals else None,
        },
    }
