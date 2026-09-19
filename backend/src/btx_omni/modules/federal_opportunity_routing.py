"""Deterministic federal opportunity decomposition, durability, and routing.

The service ranks evidence-backed routes. It does not establish awards,
supplier status, source approval, capacity, or customer participation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from btx_omni.domain.accounts import AccountRelationship

TOKEN = re.compile(r"[a-z0-9][a-z0-9-]+")
STOP = frozenset({"and", "the", "for", "with", "from", "this", "that", "services", "notice", "support"})


def _tokens(*values: object) -> set[str]:
    return {
        token
        for token in TOKEN.findall(" ".join(str(value or "") for value in values).casefold())
        if len(token) > 2 and token not in STOP
    }


def procurement_stage(raw: object, *, active: object = None) -> dict[str, str]:
    value = str(raw or "").strip()
    key = value.casefold().replace("-", " ").replace("_", " ")
    code = {
        "r": "SOURCES_SOUGHT",
        "sources sought": "SOURCES_SOUGHT",
        "sources sought notice": "SOURCES_SOUGHT",
        "p": "PRE_SOLICITATION",
        "presolicitation": "PRE_SOLICITATION",
        "pre solicitation": "PRE_SOLICITATION",
        "o": "SOLICITATION",
        "k": "SOLICITATION",
        "solicitation": "SOLICITATION",
        "combined synopsis/solicitation": "SOLICITATION",
        "a": "AWARD",
        "award notice": "AWARD",
        "award": "AWARD",
        "s": "SPECIAL_NOTICE",
        "special notice": "SPECIAL_NOTICE",
        "modification": "MODIFICATION",
    }.get(key, "UNCLASSIFIED")
    if str(active).casefold() in {"no", "false", "inactive", "archived"}:
        code = "INACTIVE"
    labels = {
        "SOURCES_SOUGHT": "Shape the requirement",
        "PRE_SOLICITATION": "Prepare to compete",
        "SOLICITATION": "Open for response",
        "SPECIAL_NOTICE": "Special notice",
        "AWARD": "Recently awarded",
        "MODIFICATION": "Award or requirement change",
        "INACTIVE": "Inactive or archived",
        "UNCLASSIFIED": "Stage needs review",
    }
    explanations = {
        "SOURCES_SOUGHT": "Government market research; this is not an open bid.",
        "PRE_SOLICITATION": "A future competition is expected; response terms may still change.",
        "SOLICITATION": "The source is accepting a formal response, subject to its stated deadline.",
        "SPECIAL_NOTICE": "The source-defined purpose must be reviewed before taking action.",
        "AWARD": "The source reports a completed government award.",
        "MODIFICATION": "The source reports a change to an existing award or requirement.",
        "INACTIVE": "The source no longer presents this notice as active.",
        "UNCLASSIFIED": "The source label has not yet been mapped to a procurement stage.",
    }
    return {"code": code, "label": labels[code], "explanation": explanations[code], "source_label": value or "Unavailable"}


def technical_decomposition(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    award = data.get("award") if isinstance(data.get("award"), dict) else {}
    description = str(payload.get("description") or payload.get("descriptionText") or payload.get("synopsis") or "")
    def value(*keys: str):
        return next((payload.get(key) for key in keys if payload.get(key) not in (None, "")), None)
    nsn_match = re.search(r"\bNSN\s*[:#-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{3}-[0-9]{4}[A-Z]{0,2})", description, re.IGNORECASE)
    part_match = re.search(r"\b(?:part|p/n)\s*(?:number|no\.?|#)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,})", description, re.IGNORECASE)
    qty_match = re.search(r"\b(?:quantity|qty)\s*[:#-]?\s*([0-9][0-9,]*)", description, re.IGNORECASE)
    return {
        "requirement": value("title") or "Federal requirement",
        "program_or_platform": value("program", "platform"),
        "end_item": value("endItem", "end_item"),
        "nsn": value("nsn", "nationalStockNumber") or (nsn_match.group(1) if nsn_match else None),
        "part_number": value("partNumber", "part_number") or (part_match.group(1) if part_match else None),
        "psc": value("classificationCode", "psc"),
        "estimated_quantity": value("quantity", "estimatedQuantity") or (qty_match.group(1).replace(",", "") if qty_match else None),
        "technical_data": value("technicalData", "technical_data"),
        "qualification_requirements": value("sourceApproval", "qualificationRequirements"),
        "awardee": award.get("awardee") if award else None,
        "evidence_state": "SOURCE_STATED",
        "remaining_unknowns": [
            label for label, item in (
                ("Program or platform", value("program", "platform")),
                ("NSN", value("nsn", "nationalStockNumber") or (nsn_match.group(1) if nsn_match else None)),
                ("Part number", value("partNumber", "part_number") or (part_match.group(1) if part_match else None)),
                ("Technical-data availability", value("technicalData", "technical_data")),
                ("Source approval or qualification", value("sourceApproval", "qualificationRequirements")),
            ) if item in (None, "")
        ],
    }


def _capability_matches(text_tokens: set[str], environment: Any) -> list[dict]:
    matches = []
    for capability in environment.capabilities:
        candidate = _tokens(capability.name, capability.description, *capability.processes)
        overlap = sorted(text_tokens & candidate)
        if overlap:
            matches.append({
                "capability_id": capability.id,
                "capability_name": capability.name,
                "business_unit_ids": list(capability.business_units),
                "matched_terms": overlap,
                "state": "FIT_HYPOTHESIS_REQUIRES_VALIDATION",
            })
    return sorted(matches, key=lambda item: (-len(item["matched_terms"]), item["capability_id"]))[:8]


def _account_matches(text_tokens: set[str], environment: Any) -> list[tuple[Any, list[str]]]:
    result = []
    for account in environment.accounts:
        aliases = [account.legal_name]
        if account.public_identity:
            aliases.extend(item.value for item in account.public_identity.aliases)
        matched = [name for name in aliases if _tokens(name) and _tokens(name) <= text_tokens]
        program_matches = [program.name for program in environment.programs if program.account_id == account.id and _tokens(program.name) & text_tokens]
        if matched or program_matches:
            result.append((account, [*matched, *program_matches]))
    return result


def route_opportunity(opportunity: dict[str, Any], *, environment: Any, partnerships: set[str] | None = None) -> list[dict]:
    partnerships = partnerships or set()
    text_tokens = _tokens(opportunity.get("title"), opportunity.get("description"), opportunity.get("technical", {}).get("program_or_platform"), opportunity.get("technical", {}).get("part_number"))
    capabilities = _capability_matches(text_tokens, environment)
    accounts = _account_matches(text_tokens, environment)
    routes: list[dict] = []
    stage = opportunity["stage"]["code"]
    timing = 2 if stage == "SOLICITATION" else 1 if stage in {"SOURCES_SOUGHT", "PRE_SOLICITATION"} else 0
    if capabilities:
        routes.append({
            "route_type": "DIRECT_BTX",
            "label": "Direct BTX pursuit to validate",
            "score": min(100, 35 + 8 * len(capabilities) + 5 * timing),
            "evidence_state": "HYPOTHESIS",
            "why": f"{len(capabilities)} BTX capability record(s) share terms with this requirement.",
            "unknowns": ["Technical-data access", "Source approval", "Current capacity and economics"],
            "governed_action": "Ask engineering and contracts to validate manufacturability, qualification, technical-data access and response timing.",
            "account_id": None,
            "business_unit_ids": sorted({bu for item in capabilities for bu in item["business_unit_ids"]}),
        })
    for account, matched in accounts:
        is_customer = account.relationship in {AccountRelationship.CURRENT_CUSTOMER, AccountRelationship.FORMER_CUSTOMER}
        route_type = "STRATEGIC_PARTNER" if account.id in partnerships else "CUSTOMER_EXPANSION" if is_customer else "NEW_PROSPECT"
        label = {"STRATEGIC_PARTNER": "Joint pursuit to validate", "CUSTOMER_EXPANSION": "Customer expansion or advisory route", "NEW_PROSPECT": "Prospect development route"}[route_type]
        routes.append({
            "route_type": route_type,
            "label": label,
            "score": min(100, 40 + 8 * min(3, len(matched)) + (12 if is_customer else 5)),
            "evidence_state": "SUPPORTED_CONTEXT_REQUIRES_VALIDATION",
            "why": "The source or recorded program context matches " + ", ".join(matched[:3]) + ".",
            "unknowns": ["Role in this requirement", "Buying or teaming authority", "Current pursuit status"],
            "governed_action": "Validate the organization’s role and review related internal records before outreach.",
            "account_id": account.id,
            "account_name": account.legal_name,
            "business_unit_ids": [],
        })
    if not routes or stage in {"SOURCES_SOUGHT", "SPECIAL_NOTICE", "UNCLASSIFIED"}:
        routes.append({
            "route_type": "MARKET_WATCH",
            "label": "Capability investment or market watch",
            "score": 30 + (10 if opportunity.get("durability", {}).get("state") == "POTENTIAL_RECURRING" else 0),
            "evidence_state": "RESEARCH_REQUIRED",
            "why": "No decision-ready direct, customer, partner or prospect route is established.",
            "unknowns": ["Demand recurrence", "Qualification cost", "Addressable BTX process fit"],
            "governed_action": "Retain the notice and investigate recurrence, qualification and related-part-family demand.",
            "account_id": None,
            "business_unit_ids": [],
        })
    return sorted(routes, key=lambda item: (-item["score"], item["route_type"], item.get("account_id") or ""))


def durability_assessment(opportunity: dict[str, Any], awards: list[dict[str, Any]]) -> dict:
    technical = opportunity["technical"]
    keys = {str(technical.get(key) or "").casefold() for key in ("nsn", "part_number", "program_or_platform")}
    keys.discard("")
    related = [award for award in awards if keys and keys & _tokens(award.get("description"))]
    years = sorted({award.get("fiscal_year") for award in related if award.get("fiscal_year")})
    state = "POTENTIAL_RECURRING" if len(years) >= 2 or len(related) >= 3 else "ONE_TIME_OR_UNKNOWN"
    return {
        "state": state,
        "label": "Potential recurring sustainment program" if state == "POTENTIAL_RECURRING" else "Durability not yet established",
        "historical_award_count": len(related),
        "observed_fiscal_years": years,
        "evidence_coverage": len([value for value in (technical.get("nsn"), technical.get("part_number"), related) if value]) / 3,
        "explanation": "Historical demand supports further investigation, but qualification cost and source approval remain unresolved." if state == "POTENTIAL_RECURRING" else "One notice is not enough to establish recurring demand; historical awards and platform service life remain to be verified.",
        "missing_inputs": ["Platform service life", "Approved-source concentration", "Qualification cost and time"],
    }


def build_assessment(opportunity: dict[str, Any], *, environment: Any, awards: list[dict[str, Any]], partnerships: set[str] | None, now: datetime) -> dict:
    source_revision = opportunity.get("source_revision") or opportunity["canonical_source_id"]
    opportunity = dict(opportunity)
    opportunity["technical"] = technical_decomposition(opportunity.get("source_payload", {}))
    opportunity["durability"] = durability_assessment(opportunity, awards)
    routes = route_opportunity(opportunity, environment=environment, partnerships=partnerships)
    source = {
        "canonical_source_id": opportunity.get("canonical_source_id"),
        "title": opportunity.get("title"),
        "official_source_url": opportunity.get("official_source_url"),
        "agency": opportunity.get("agency"),
        "office": opportunity.get("office"),
        "posted_date": opportunity.get("posted_date"),
        "response_deadline": opportunity.get("response_deadline"),
    }
    input_revision = hashlib.sha256(json.dumps({
        "source": source_revision,
        "source_context": source,
        "technical": opportunity["technical"],
        "routes": routes,
        "durability": opportunity["durability"],
    }, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "opportunity_id": opportunity["opportunity_id"],
        "source_revision": source_revision,
        "input_revision": input_revision,
        "stage": opportunity["stage"],
        "technical": opportunity["technical"],
        "durability": opportunity["durability"],
        "routes": routes,
        "recommended_route": routes[0] if routes else None,
        "supporting_evidence_count": 1 + len(routes),
        "assessed_at": now.isoformat(),
        "policy_version": "BTX_FEDERAL_ROUTING_POC_1",
        "source": source,
        "evidence_references": [value for value in (source["canonical_source_id"],) if value],
    }
