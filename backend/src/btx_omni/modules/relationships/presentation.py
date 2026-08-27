"""Deterministic seller language over canonical relationship paths."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from btx_omni.modules.relationships.service import RelationshipHop

RELATIONSHIP_POLICY: dict[str, tuple[str, str, str]] = {
    "PARENT_CHILD": ("Organizational relationship", "The canonical record documents an organizational connection between these Customers.", "Review the documented organizational relationship and its evidence before planning outreach."),
    "PARENT_CHILD_REVERSE": ("Organizational relationship", "The canonical record documents an organizational connection between these Customers.", "Review the documented organizational relationship and its evidence before planning outreach."),
    "SHARED_PROGRAM": ("Shared program", "Both Customers are canonically associated with the same program context.", "Inspect the shared program evidence before using it to shape outreach."),
    "SHARED_PROGRAM_REVERSE": ("Shared program", "Both Customers are canonically associated with the same program context.", "Inspect the shared program evidence before using it to shape outreach."),
    "COMPETITOR_ON_PROGRAM": ("Program competitor relationship", "The canonical record places these Customers in the same competitive program context.", "Review the program evidence and differentiation context before outreach."),
    "COMPETITOR_ON_PROGRAM_REVERSE": ("Program competitor relationship", "The canonical record places these Customers in the same competitive program context.", "Review the program evidence and differentiation context before outreach."),
    "SHARED_PRIME": ("Shared prime relationship", "The canonical record identifies a shared prime context relevant to account planning.", "Inspect the shared-prime evidence before using it as commercial context."),
    "SHARED_PRIME_REVERSE": ("Shared prime relationship", "The canonical record identifies a shared prime context relevant to account planning.", "Inspect the shared-prime evidence before using it as commercial context."),
    "GEOGRAPHIC_CLUSTER": ("Shared geographic cluster", "Verified location proximity may inform territory planning but does not establish a business relationship.", "Review the location evidence; do not treat proximity as an introduction path."),
    "GEOGRAPHIC_CLUSTER_REVERSE": ("Shared geographic cluster", "Verified location proximity may inform territory planning but does not establish a business relationship.", "Review the location evidence; do not treat proximity as an introduction path."),
    "OPERATES": ("Customer facility", "Public evidence links this Customer to the named operating location.", "Inspect the facility evidence before using it in account planning."),
    "OPERATED_BY": ("Customer facility", "Public evidence links this operating location to the Customer.", "Inspect the facility evidence before using it in account planning."),
    "HAS_CONTACT": ("Recorded contact association", "A canonical SAMPLE CRM record associates this contact role with the Customer; it does not establish an introduction path.", "Review the contact record and provenance before any outreach."),
    "CONTACT_FOR": ("Recorded contact association", "A canonical SAMPLE CRM record associates this contact role with the Customer; it does not establish an introduction path.", "Review the contact record and provenance before any outreach."),
    "HAS_COMMERCIAL_CONTEXT": ("Commercial history", "SAMPLE commercial context exists for this Customer.", "Review the governed commercial history and current owner context."),
    "COMMERCIAL_CONTEXT_FOR": ("Commercial history", "SAMPLE commercial context exists for this Customer.", "Review the governed commercial history and current owner context."),
    "CUSTOMER_OF": ("Business-unit Customer relationship", "SAMPLE commercial context links this Customer to a BTX business unit.", "Review the relevant internal business-unit context before planning outreach."),
    "HAS_CUSTOMER": ("Business-unit Customer relationship", "SAMPLE commercial context links this business unit to the Customer.", "Review the relevant internal business-unit context before planning outreach."),
    "QUOTED_WITH": ("Quote history", "A canonical SAMPLE quote record connects this Customer to the related record.", "Review the quote history and responsible business-unit context."),
    "QUOTE_FOR": ("Quote history", "A canonical SAMPLE quote record connects this quote to the Customer.", "Review the quote history and responsible business-unit context."),
    "HAS_QUOTE": ("Quote history", "A canonical SAMPLE quote record connects this business unit to the Customer.", "Review the quote history and responsible business-unit context."),
    "ORDERED_WITH": ("Order history", "A canonical SAMPLE order record connects this Customer to the related record.", "Review the order history and responsible business-unit context."),
    "ORDER_FOR": ("Order history", "A canonical SAMPLE order record connects this order to the Customer.", "Review the order history and responsible business-unit context."),
    "PARTICIPATES_IN": ("Program participation", "Canonical evidence associates this Customer with the named program.", "Inspect the program evidence before using it in account planning."),
    "HAS_PARTICIPANT": ("Program participation", "Canonical evidence associates this program with the Customer.", "Inspect the program evidence before using it in account planning."),
    "RELATED_TO_PROGRAM": ("Program relationship", "Public evidence relates this Customer to the named program.", "Inspect the program evidence before using it in account planning."),
    "PROGRAM_FOR": ("Program relationship", "Public evidence relates this program to the Customer.", "Inspect the program evidence before using it in account planning."),
    "REQUIRES_COMPONENT_CLASS": ("Program component need", "Canonical evidence links the program to this component class.", "Review the component requirement and supporting evidence."),
    "REQUIRED_BY_PROGRAM": ("Program component need", "Canonical evidence links this component class to the program.", "Review the component requirement and supporting evidence."),
    "CAPABILITY_MATCH": ("BTX capability alignment", "Canonical component data maps this requirement to a BTX business unit capability.", "Review the relevant business unit and validate fit before outreach."),
    "MATCHES_COMPONENT_CLASS": ("BTX capability alignment", "Canonical component data maps this BTX business unit to the requirement.", "Review the relevant business unit and validate fit before outreach."),
    "HAS_CAPABILITY": ("BTX capability", "Canonical BTX data records this capability for the business unit.", "Review the capability and responsible business unit."),
    "CAPABILITY_OF": ("BTX capability", "Canonical BTX data links this capability to the business unit.", "Review the capability and responsible business unit."),
}


def seller_relationship_semantics(relationship_type: str) -> tuple[str, str, str]:
    """Return governed copy without exposing raw predicates to sellers."""
    return RELATIONSHIP_POLICY.get(
        relationship_type,
        (
            "Recorded relationship",
            "A canonical relationship record connects these entities.",
            "Inspect the evidence before using this relationship in account planning.",
        ),
    )


def _evidence(hops: tuple[RelationshipHop, ...]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for hop in hops:
        provenance = hop.provenance
        key = (provenance.source_record_id if provenance else None, provenance.source_url if provenance else None)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "source_ids": list(hop.source_ids),
            "source_system": provenance.source_system if provenance else None,
            "source_record_id": provenance.source_record_id if provenance else None,
            "source_url": provenance.source_url if provenance else None,
            "observed_at": provenance.observed_at if provenance else None,
            "classification": provenance.classification if provenance else None,
            "data_mode": provenance.data_mode if provenance else None,
            "synthetic": provenance.synthetic if provenance else None,
            "evidence_state": hop.evidence_state,
        })
    return items


class SellerRelationshipPresentationService:
    """Projects raw paths into deterministic, provenance-preserving seller DTOs."""

    def present_path(self, path: dict[str, Any]) -> dict[str, Any]:
        hops: tuple[RelationshipHop, ...] = path["hops"]
        policies = [seller_relationship_semantics(hop.relationship_type) for hop in hops]
        steps = [asdict(hops[0].from_entity), *(asdict(hop.to_entity) for hop in hops)]
        for step in steps:
            step["display_name"] = {
                "quote": "Quote record",
                "order": "Order record",
                "commercial_context": "Commercial context",
            }.get(step["kind"], step["name"])
        labels = list(dict.fromkeys(policy[0] for policy in policies))
        evidence = _evidence(hops)
        is_sample = any(
            getattr(item["classification"], "value", item["classification"]) == "INTERNAL_COMMERCIAL"
            or getattr(item["data_mode"], "value", item["data_mode"]) == "SAMPLE"
            for item in evidence
        )
        return {
            "path_id": path["path_id"],
            "direct": len(hops) == 1,
            "step_count": len(hops),
            "steps": steps,
            "connection_label": " via ".join(labels),
            "summary": " → ".join(step["display_name"] for step in steps),
            "why_it_matters": " ".join(dict.fromkeys(policy[1] for policy in policies)),
            "suggested_move": policies[-1][2],
            "evidence_state": path["overall_evidence_state"],
            "presentation_state": path["presentation_state"],
            "truth_label": "SAMPLE BTX commercial context" if is_sample else "Canonical relationship evidence",
            "evidence": evidence,
        }

    def present(self, result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        return {
            "seller_direct_relationships": [self.present_path(path) for path in result["direct_relationships"]],
            "seller_paths": [self.present_path(path) for path in result["paths"]],
        }
