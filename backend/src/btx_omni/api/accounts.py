from fastapi import APIRouter, Depends, HTTPException, Query

from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.accounts.customer_360 import customer_360_projection
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.modules.relationships.presentation import (
    SellerRelationshipPresentationService,
)
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    SellerAttractivenessProjection,
    seller_attractiveness_projection,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _seller_attractiveness(projection: SellerAttractivenessProjection) -> dict:
    return {"score": projection.score, "coverage": projection.coverage, "status": projection.status,
            "score_unit": projection.score_unit, "configuration_version": projection.configuration_version,
            "hypothesis": projection.hypothesis, "data_mode": projection.data_mode,
            "interpretation_note": projection.interpretation_note,
            "factors": [{"name": item.key, "configured_weight": item.configured_weight, "score": item.factor_score,
                         "contribution": item.contribution, "input_coverage": item.input_coverage,
                         "missing": item.missing, "gaps": item.missing_subfactors, "evidence_ids": item.evidence_ids}
                        for item in projection.factors], "missingness": projection.missingness,
            "evidence_ids": projection.evidence_ids, "exclusion_reason": projection.exclusion_reason}


def get_runtime() -> PocRuntime:
    from btx_omni.app import runtime
    return runtime


@router.get("")
def accounts(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    facilities = {item.account_id: item for item in sample.facilities}
    contexts = {item.account_id: item for item in sample.commercial_contexts}
    records = []
    for item in sample.accounts:
        scenario = sample.priority_scenarios.get(item.id) or sample.rich_scenarios.get(item.id)
        projection = seller_attractiveness_projection(AccountAttractivenessInputs(sample.scoring_inputs.get(item.id, {})), calculated_at=runtime.observed_at(), excluded=bool(scenario and scenario.exclusion_reason), exclusion_reason=scenario.exclusion_reason if scenario else None)
        records.append({"id": item.id, "name": item.legal_name, "relationship": item.relationship, "industries": item.industries, "secondary_classifications": item.secondary_classifications, "domain": item.domain, "contact_role_families": item.contact_role_families, "public_research_state": item.public_research_state, "public_identity_state": item.public_identity.verification_state if item.public_identity else "UNVERIFIED", "research_account_id": item.research_account_id, "public_relationship_state": item.public_relationship.state if item.public_relationship else "NO_RESEARCH", "prospect_research_priority": item.prospect_research_priority, "prospect_rationale": item.prospect_rationale, "btx_top_100": item.btx_top_100, "btx_top_100_provenance": item.btx_top_100_provenance, "is_rich_scenario": item.id in sample.rich_scenarios or item.id in sample.priority_scenarios, "truth_state": "PUBLICLY_VERIFIED" if item.id in sample.rich_scenarios else ("REFERENCE_SOURCE" if item.public_research_state == "SANITIZED_REFERENCE" else "RESEARCHED_PUBLIC"), "location": facilities.get(item.id), "attractiveness": projection.score, "account_attractiveness": _seller_attractiveness(projection), "business_unit": contexts[item.id].business_unit if item.id in contexts else None, "commercial_context_state": "SAMPLE" if item.id in contexts else "UNAVAILABLE", "provenance": item.provenance.source_record_id if item.provenance else None})
    return {"poc_mode": "REAL_PUBLIC_MARKET_DATA_SIMULATED_BTX_CONTEXT", "accounts": records}


@router.get("/{account_id}")
def account_360(account_id: str, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    account = next((item for item in sample.accounts if item.id == account_id), None)
    if account is None:
        raise HTTPException(404, "Canonical Customer not found.")
    observed = runtime.observed_at()
    commercial = runtime.commercial_account_snapshot(account_id)
    contexts = commercial.commercial_context
    paperless_accounts = commercial.paperless_accounts
    public_facilities = [item for item in sample.facilities if item.account_id == account_id]
    quotes = commercial.quotes
    crm = commercial.crm
    signals = [item for item in intelligence_signals(runtime) if item["account_id"] == account.id]
    matches = [match_component_to_quote(component, quote) for component in sample.matching_components for quote in sample.matching_quotes if component.account_id == account_id and quote.account_id == account_id]
    scenario = sample.priority_scenarios.get(account_id) or sample.rich_scenarios.get(account_id)
    selections = sample.scoring_inputs.get(account_id, {})
    projection = seller_attractiveness_projection(AccountAttractivenessInputs(selections), calculated_at=observed, excluded=bool(scenario and scenario.exclusion_reason), exclusion_reason=scenario.exclusion_reason if scenario else None)
    alerts = [item for item in CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=observed, orders=sample.orders) if item.account_id == account_id]
    return {"account": account, "public_identity": account.public_identity, "public_identity_state": account.public_identity.verification_state if account.public_identity else "UNVERIFIED", "public_relationship": account.public_relationship, "prospect_research_priority": account.prospect_research_priority, "prospect_rationale": account.prospect_rationale, "reason_for_attention": scenario.reason_for_attention if scenario else account.prospect_rationale, "recommended_next_step": scenario.recommended_next_step if scenario else "Research public evidence before recommending outreach.", "truth_categories": {"public": "PUBLICLY_VERIFIED" if account.research_account_id else ("SANITIZED_REFERENCE_SOURCE" if account.public_research_state == "SANITIZED_REFERENCE" else "UNAVAILABLE"), "btx": "SIMULATED_BTX_CONTEXT" if scenario or contexts else "UNAVAILABLE"}, "commercial_source_states": commercial.source_states, "public_contacts": account.public_contacts, "public_facilities": public_facilities, "prism_commercial_context": contexts, "paperless_accounts": paperless_accounts, "paperless_quotes": quotes, "orders": commercial.orders, "crm": crm, "account_attractiveness": _seller_attractiveness(projection), "alerts": alerts, "intelligence": signals, "matching": matches, "customer_360": customer_360_projection(account_id=account_id, sample=sample, commercial=commercial, signals=signals), "provenance": account.provenance, "missingness": list(projection.missingness) + (["No linked CRM company for this canonical Customer"] if not crm["companies"] else [])}


@router.get("/{account_id}/relationships")
def account_relationships(account_id: str, depth: int = Query(default=2, ge=1, le=4), runtime: PocRuntime = Depends(get_runtime)) -> dict:
    try:
        result = RelationshipIntelligenceService(runtime.environment()).account_relationships(account_id, depth=depth)
        return {**result, **SellerRelationshipPresentationService().present(result)}
    except KeyError as exc:
        raise HTTPException(404, "Canonical Customer not found.") from exc
