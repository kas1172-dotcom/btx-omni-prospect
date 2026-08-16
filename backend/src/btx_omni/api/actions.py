from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.integrations.hubspot.contracts import SampleHubSpotAdapter
from btx_omni.modules.work.service import WorkStatus

router = APIRouter(prefix="/actions", tags=["actions"])


class CreateAction(BaseModel):
    account_id: str
    summary: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    actor_id: str
    opportunity_id: str | None = None
    owner_id: str | None = None
    priority: str = "MEDIUM"
    due_date: date | None = None
    notes: str | None = None


class TransitionAction(BaseModel):
    actor_id: str
    owner_id: str | None = None
    note: str | None = None


@router.post("")
def create(body: CreateAction, runtime: PocRuntime = Depends(get_runtime)):
    runtime.environment()
    return runtime.work.create(**body.model_dump(), occurred_at=runtime.observed_at())


@router.get("/{item_id}/audit")
def audit(item_id: str, runtime: PocRuntime = Depends(get_runtime)):
    return {"events": runtime.work.audit(item_id)}


@router.post("/{item_id}/crm-preview")
def crm_preview(item_id: str, runtime: PocRuntime = Depends(get_runtime)):
    return runtime.work.preview_crm_action(item_id, SampleHubSpotAdapter({}))


@router.post("/{item_id}/crm-execute")
def crm_execute(item_id: str, confirmed: bool = False, runtime: PocRuntime = Depends(get_runtime)):
    if not confirmed:
        raise HTTPException(409, "Explicit human confirmation is required before CRM execution.")
    preview = runtime.work.preview_crm_action(item_id, SampleHubSpotAdapter({}))
    return runtime.work.confirm_and_execute_crm_action(preview, SampleHubSpotAdapter({}))


@router.post("/{item_id}/{status}")
def transition(item_id: str, status: WorkStatus, body: TransitionAction, runtime: PocRuntime = Depends(get_runtime)):
    runtime.environment()
    try:
        return runtime.work.transition(item_id, status, **body.model_dump(), occurred_at=runtime.observed_at())
    except KeyError as error:
        raise HTTPException(404, "Action not found.") from error
