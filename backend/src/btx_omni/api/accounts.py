from fastapi import APIRouter, Depends, HTTPException

from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.intelligence.signals import normalize_signal
from btx_omni.modules.matching.commercial import match_component_to_quote
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_runtime() -> PocRuntime:
    from btx_omni.app import runtime
    return runtime


@router.get("")
def accounts(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    facilities = {item.account_id: item for item in sample.facilities}
    return {"data_mode": "SAMPLE", "accounts": [{"id": item.id, "name": item.legal_name, "relationship": item.relationship, "industries": item.industries, "domain": item.domain, "contact_role_families": item.contact_role_families, "public_research_state": item.public_research_state, "public_identity_state": item.public_identity.verification_state if item.public_identity else "UNVERIFIED", "location": facilities[item.id], "provenance": item.provenance.source_record_id if item.provenance else None} for item in sample.accounts]}


@router.get("/{account_id}")
def account_360(account_id: str, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    sample = runtime.environment()
    account = next((item for item in sample.accounts if item.id == account_id), None)
    if account is None:
        raise HTTPException(404, "Canonical account not found.")
    observed = runtime.observed_at()
    contexts = [item for item in sample.commercial_contexts if item.account_id == account_id]
    paperless_accounts = [item for item in sample.paperless_accounts if item.canonical_account_id == account_id]
    quotes = [item for item in sample.quotes if item.account_id == account_id]
    crm = next((item for item in sample.crm_contexts if item.account_id == account_id), None)
    signals = [normalize_signal(item, account_name_to_id={value.legal_name: value.id for value in sample.accounts}, provenance=account.provenance) for item in sample.intelligence_events if item.account_name == account.legal_name]
    matches = [match_component_to_quote(component, quote) for component in sample.matching_components for quote in sample.matching_quotes if component.account_id == account_id and quote.account_id == account_id]
    score = calculate_account_attractiveness(AccountAttractivenessInputs(sample.scoring_inputs[account_id]), evidence_ids=(account.provenance.source_record_id,), calculated_at=observed)
    alerts = [item for item in CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=observed) if item.account_id == account_id]
    return {"account": account, "public_identity": account.public_identity, "public_identity_state": account.public_identity.verification_state if account.public_identity else "UNVERIFIED", "prism_commercial_context": contexts, "paperless_accounts": paperless_accounts, "paperless_quotes": quotes, "crm": crm, "account_attractiveness": score, "alerts": alerts, "intelligence": signals, "matching": matches, "provenance": account.provenance, "missingness": list(score.missingness) + (["CRM context unavailable"] if crm is None else [])}
