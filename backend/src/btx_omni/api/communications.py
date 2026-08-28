from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import GroundedSynthesisRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import ApprovalStatus, Principal
from btx_omni.integrations.communications import (
    DeliveryNotConfiguredError,
    UnconfiguredDeliveryAdapter,
)
from btx_omni.modules.communications.service import (
    CommunicationConflictError,
    CommunicationForbiddenError,
    CommunicationNotFoundError,
)

router = APIRouter(prefix="/communications", tags=["communications"])


class DraftCreate(BaseModel):
    account_id: str
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    recipients: tuple[str, ...] = ()
    trigger: str | None = None
    evidence_ids: tuple[str, ...] = ()
    idempotency_key: str | None = None


class DraftEdit(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1)
    recipients: tuple[str, ...] | None = None


class ApprovalDecision(BaseModel):
    decision: ApprovalStatus


class DraftAssist(BaseModel):
    instruction: str = Field(min_length=1, max_length=500)


def _error(error: Exception) -> HTTPException:
    if isinstance(error, CommunicationNotFoundError):
        return HTTPException(404, "Communication draft not found.")
    if isinstance(error, CommunicationForbiddenError):
        return HTTPException(403, str(error))
    if isinstance(error, (CommunicationConflictError, DeliveryNotConfiguredError)):
        return HTTPException(409, str(error))
    return HTTPException(400, str(error))


def _allowed_recipients(runtime: PocRuntime, account_id: str) -> frozenset[str]:
    account = next((item for item in runtime.environment().accounts if item.id == account_id), None)
    if not account:
        raise HTTPException(404, "Canonical Customer not found.")
    return frozenset(
        email.strip().casefold()
        for contact in account.public_contacts
        if (email := contact.public_email)
    )


def _validate_recipients(runtime: PocRuntime, account_id: str, recipients: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(item.strip().casefold() for item in recipients if item.strip()))
    if not set(normalized) <= _allowed_recipients(runtime, account_id):
        raise HTTPException(422, "Recipients must use an explicitly available professional email for this Customer.")
    return normalized


@router.get("")
def list_drafts(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    return {
        "items": runtime.communications.list(current),
        "principal": current,
        "delivery": {"state": "NOT_CONFIGURED", "label": "Delivery not configured"},
    }


@router.post("")
def create_draft(body: DraftCreate, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    recipients = _validate_recipients(runtime, body.account_id, body.recipients)
    try:
        return runtime.communications.create(**body.model_dump(exclude={"recipients"}), recipients=recipients, principal=current, occurred_at=runtime.observed_at())
    except (CommunicationConflictError, ValueError) as error:
        raise _error(error) from error


@router.patch("/{draft_id}")
def edit_draft(draft_id: str, body: DraftEdit, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    draft = runtime.communications.repository.get(draft_id)
    if not draft:
        raise HTTPException(404, "Communication draft not found.")
    values = body.model_dump(exclude_unset=True)
    if "recipients" in values:
        values["recipients"] = _validate_recipients(runtime, draft.account_id, tuple(values["recipients"]))
    try:
        return runtime.communications.edit(draft_id, **values, principal=current, occurred_at=runtime.observed_at())
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/assist")
def assist_draft(draft_id: str, body: DraftAssist, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    draft = runtime.communications.repository.get(draft_id)
    if not draft:
        raise HTTPException(404, "Communication draft not found.")
    account = next(item for item in runtime.environment().accounts if item.id == draft.account_id)
    provider = get_ai_provider(AiConfig.from_settings(runtime.settings))
    provider_status = "NOT_CONFIGURED"
    revised = draft.body
    model = None
    if provider.configured:
        try:
            result = provider.synthesize(GroundedSynthesisRequest(
                question=f"Revise this outreach draft as instructed: {body.instruction}. Do not add recipients, unsupported facts, or claims.",
                governed_answer=f"Customer: {account.legal_name}. Current draft: {draft.body}",
                evidence_ids=draft.evidence_ids,
                missingness=("Recipient availability remains governed by the application.",),
            ))
            revised, provider_status, model = result.content, "AVAILABLE", result.model
        except (RuntimeError, TimeoutError, ValueError):
            provider_status = "UNAVAILABLE"
    try:
        updated = runtime.communications.edit(draft_id, body=revised, principal=current, occurred_at=runtime.observed_at(), ai_metadata={"provider": "gemini" if model else "deterministic", "model": model or "none", "status": provider_status})
    except Exception as error:
        raise _error(error) from error
    return {"draft": updated, "provider_status": provider_status, "message": "Draft revised with governed Gemini assistance." if model else "Gemini is unavailable; the existing draft was preserved."}


@router.post("/{draft_id}/approval")
def approval(draft_id: str, body: ApprovalDecision, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return runtime.communications.decide(draft_id, body.decision, principal=current, occurred_at=runtime.observed_at())
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/preview")
def preview(draft_id: str, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return runtime.communications.preview(draft_id, principal=current, occurred_at=runtime.observed_at(), delivery=UnconfiguredDeliveryAdapter())
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/send")
def send(draft_id: str, confirmed: bool = False, idempotency_key: str = "", runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    if not idempotency_key:
        raise HTTPException(422, "An idempotency key is required.")
    try:
        return runtime.communications.send(draft_id, principal=current, occurred_at=runtime.observed_at(), confirmed=confirmed, idempotency_key=idempotency_key, delivery=UnconfiguredDeliveryAdapter())
    except Exception as error:
        raise _error(error) from error


@router.get("/{draft_id}/history")
def history(draft_id: str, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)) -> dict:
    try:
        return {"events": runtime.communications.history(draft_id, current)}
    except Exception as error:
        raise _error(error) from error
