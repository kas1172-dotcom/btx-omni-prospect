"""Permissioned bounded retrieval of canonical commercial evidence and references."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.actions import _handle
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.scoring.families import customer_risk_projection
from btx_omni.modules.work.commercial_followup import confirm_followup, followup_preview
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    ActionNotFoundError,
)
from btx_omni.monitor.briefs import signal_briefs_for_monitor
from btx_omni.persistence.commercial_import import digest
from btx_omni.persistence.commercial_schema import COLLECTION_TABLES
from btx_omni.providers.research.enriched_evidence import public_sources

router = APIRouter(prefix="/accounts", tags=["commercial"])


class ConfirmFollowup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/{account_id}/commercial/follow-ups/{action_id}/preview")
def preview_followup(account_id: str, action_id: str, response: Response,
                     actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    sample = runtime.environment()
    response.headers["Cache-Control"] = "private, no-store"
    if account_id not in sample.commercial_ledgers:
        raise HTTPException(404, "No canonical commercial account.")
    try:
        return followup_preview(sample.commercial_ledgers[account_id], account_id=account_id,
                                action_id=action_id, revision=sample.commercial_revision, principal=actor, work=runtime.work)
    except (ActionConflictError, ActionForbiddenError, ActionNotFoundError) as error:
        raise _handle(error) from error


@router.post("/{account_id}/commercial/follow-ups/{action_id}/confirm")
def create_followup(account_id: str, action_id: str, body: ConfirmFollowup, response: Response,
                    actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    sample = runtime.environment()
    response.headers["Cache-Control"] = "private, no-store"
    if account_id not in sample.commercial_ledgers:
        raise HTTPException(404, "No canonical commercial account.")
    try:
        return confirm_followup(sample.commercial_ledgers[account_id], account_id=account_id,
                                action_id=action_id, revision=sample.commercial_revision, principal=actor,
                                work=runtime.work, preview_token=body.preview_token, occurred_at=runtime.observed_at())
    except (ActionConflictError, ActionForbiddenError, ActionNotFoundError, ValueError) as error:
        raise _handle(error) from error


@router.get("/{account_id}/commercial/{collection}")
def commercial_evidence(
    account_id: str, collection: str, response: Response,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
    record_id: str | None = Query(default=None, max_length=220),
    actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime),
) -> dict:
    # The existing hosted POC has one authorized environment, not an invented
    # tenant selector. Its authenticated principal governs this detail boundary.
    sample = runtime.environment()
    response.headers["Cache-Control"] = "private, no-store"
    ledger = sample.commercial_ledgers.get(account_id)
    if ledger is None:
        raise HTTPException(404, "No persisted commercial record for this canonical account.")
    if collection == "evidence":
        if not record_id:
            raise HTTPException(422, "Choose a canonical evidence record.")
        evidence = resolve_commercial_evidence(ledger, record_id)
        if evidence is None:
            raise HTTPException(404, "Evidence is not available in the selected account scope.")
        return {"account_id": account_id, "revision": sample.commercial_revision, "as_of": ledger["as_of"], **evidence}
    if collection == "fulfillment":
        return fulfillment_state(ledger, canonical_account_id=account_id, revision=sample.commercial_revision)
    if collection == "decisions":
        account = next(a for a in sample.accounts if a.id == account_id)
        current_customer = account.relationship.value in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"}
        decisions = customer_decisions(ledger, account_id=account_id, revision=sample.commercial_revision,
                                       current_customer=current_customer,
                                       work_items=tuple(runtime.work.list(actor)))
        return {
            **decisions,
            **customer_risk_projection(
                account_id=account_id,
                current_customer=current_customer,
                internal_decision=decisions["internal_commercial_risk"],
                signal_briefs=signal_briefs_for_monitor(runtime.monitor, environment=sample),
            ),
        }
    if collection == "reference":
        return {"account_id": account_id, "revision": sample.commercial_revision,
                "reference": {k: v for k, v in ledger.items() if k not in COLLECTION_TABLES}}
    if collection == 'source_package':
        reference = runtime.commercial_repository.source_package(account_id, digest(ledger)) if runtime.commercial_repository else {
            'availability': 'DURABLE_IMPORT_NOT_CONFIGURED', 'source_metadata': None}
        return {'account_id': account_id, 'revision': sample.commercial_revision, 'reference': reference}
    if collection == "sources":
        def source_ids(value):
            if isinstance(value, dict):
                found = set(value.get("source_ids", []))
                for child in value.values():
                    found.update(source_ids(child))
                return found
            if isinstance(value, list):
                return set().union(*(source_ids(child) for child in value))
            return set()
        catalog = public_sources()
        selected = source_ids(ledger)
        return {"account_id": account_id, "revision": sample.commercial_revision,
                "sources": [catalog[sid] for sid in sorted(selected) if sid in catalog],
                "unresolved_source_ids": sorted(selected - catalog.keys())}
    if collection not in COLLECTION_TABLES:
        raise HTTPException(404, "Unknown commercial collection.")
    from btx_omni.modules.commercial.ledger import KEYS
    key = KEYS.get(collection, {"contacts": "contact_id", "supply_relationships": "relationship_id"}.get(collection))
    records = sorted(ledger[collection], key=lambda r: r[key])
    if record_id:
        records = [r for r in records if r[key] == record_id]
        if not records:
            raise HTTPException(404, "Record does not belong to the selected account.")
    return {"account_id": account_id, "collection": collection, "as_of": ledger["as_of"],
            "revision": sample.commercial_revision, "total": len(records), "offset": offset,
            "records": records[offset:offset + limit], "record_key": key,
            "next_offset": offset + limit if offset + limit < len(records) else None}
