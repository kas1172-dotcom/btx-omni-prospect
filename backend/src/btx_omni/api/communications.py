from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import GovernedDraftingRequest
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import ApprovalStatus, Principal
from btx_omni.integrations.communications import (
    DeliveryNotConfiguredError,
    UnconfiguredDeliveryAdapter,
)
from btx_omni.modules.communications.drafting import draft_governed_content
from btx_omni.modules.communications.service import (
    CommunicationConflictError,
    CommunicationForbiddenError,
    CommunicationNotFoundError,
)
from btx_omni.persistence.communications import CommunicationVersionConflict

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
    model_config = {"extra": "forbid"}
    expected_version: int = Field(ge=1)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1)
    recipients: tuple[str, ...] | None = None


class ApprovalDecision(BaseModel):
    model_config = {"extra": "forbid"}
    expected_version: int = Field(ge=1)
    decision: ApprovalStatus


class DraftAssist(BaseModel):
    model_config = {"extra": "forbid"}
    expected_version: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=500)


class DraftProposal(BaseModel):
    account_id: str
    instruction: str = Field(min_length=1, max_length=500)
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=6000)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=16)


def _drafting_request(
    account,
    instruction: str,
    *,
    subject: str | None = None,
    body: str | None = None,
    evidence_ids: tuple[str, ...] = (),
    intelligence_facts: tuple[str, ...] = (),
) -> GovernedDraftingRequest:
    facts = [
        f"Canonical Customer: {account.legal_name}. Public identity and market context are governed by Omni.",
        f"Public industries/markets: {', '.join(account.industries) or 'Unavailable'}.",
        "Do not imply BTX commercial activity, supplier status, score, relationship, or authorization unless supplied through a governed workflow.",
    ]
    facts.extend(intelligence_facts)
    return GovernedDraftingRequest(
        subject_display_name=account.legal_name,
        instruction=instruction,
        draft_kind="SELLER_COMMUNICATION",
        governed_facts=tuple(facts),
        evidence_ids=evidence_ids,
        current_subject=subject,
        current_body=body,
    )


def _intelligence_facts(runtime: PocRuntime, account_id: str, evidence_ids: tuple[str, ...]) -> tuple[str, ...]:
    repository = runtime.monitor.repository
    if not repository:
        return ()
    facts = []
    for evidence_id in evidence_ids:
        assessment = repository.intelligence_assessment_by_id(evidence_id)
        if not assessment:
            continue
        if assessment["account_id"] != account_id or not assessment["is_current"]:
            raise HTTPException(409, "The referenced Intelligence assessment changed or belongs to another Customer; refresh before drafting.")
        projection = assessment["projection"]
        facts.extend((
            f"Current Intelligence development: {projection.get('headline')}",
            f"Supported commercial implication: {projection.get('why_it_may_matter')}",
            f"Governed next step: {projection.get('recommended_action') or 'No seller action is established.'}",
            f"Material uncertainty: {'; '.join(projection.get('material_uncertainties', ())) or 'None recorded.'}",
        ))
    return tuple(facts)


def _proposal_payload(outcome) -> dict:
    return {
        "proposal": {
            "subject": outcome.proposal.subject,
            "body": outcome.proposal.body,
            "evidence_ids": outcome.proposal.evidence_ids,
        },
        "provider_status": outcome.provider_status.value,
        "assisted": outcome.assisted,
        "message": "Gemini produced a proposal. Review and save it through the governed draft workflow."
        if outcome.assisted
        else "Gemini is unavailable; manual drafting remains available and no draft was changed.",
    }


def _error(error: Exception) -> HTTPException:
    if isinstance(error, CommunicationNotFoundError):
        return HTTPException(404, "Communication draft not found.")
    if isinstance(error, CommunicationForbiddenError):
        return HTTPException(403, str(error))
    if isinstance(error, (CommunicationConflictError, CommunicationVersionConflict, DeliveryNotConfiguredError)):
        return HTTPException(409, str(error))
    return HTTPException(400, str(error))


def _allowed_recipients(runtime: PocRuntime, account_id: str) -> frozenset[str]:
    account = next(
        (item for item in runtime.environment().accounts if item.id == account_id), None
    )
    if not account:
        raise HTTPException(404, "Canonical Customer not found.")
    return frozenset(
        email.strip().casefold()
        for contact in account.public_contacts
        if (email := contact.public_email)
    )


def _validate_recipients(
    runtime: PocRuntime, account_id: str, recipients: tuple[str, ...]
) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(item.strip().casefold() for item in recipients if item.strip())
    )
    if not set(normalized) <= _allowed_recipients(runtime, account_id):
        raise HTTPException(
            422,
            "Recipients must use an explicitly available professional email for this Customer.",
        )
    return normalized


@router.get("")
def list_drafts(
    runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)
) -> dict:
    return {
        "items": runtime.communications.list(current),
        "principal": current,
        "delivery": {"state": "NOT_CONFIGURED", "label": "Delivery not configured"},
    }


@router.post("")
def create_draft(
    body: DraftCreate,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    recipients = _validate_recipients(runtime, body.account_id, body.recipients)
    try:
        return runtime.communications.create(
            **body.model_dump(exclude={"recipients"}),
            recipients=recipients,
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except (CommunicationConflictError, ValueError) as error:
        raise _error(error) from error


@router.patch("/{draft_id}")
def edit_draft(
    draft_id: str,
    body: DraftEdit,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    draft = runtime.communications.repository.get(draft_id)
    if not draft:
        raise HTTPException(404, "Communication draft not found.")
    values = body.model_dump(exclude_unset=True)
    if "recipients" in values:
        values["recipients"] = _validate_recipients(
            runtime, draft.account_id, tuple(values["recipients"])
        )
    try:
        return runtime.communications.edit(
            draft_id, **values, principal=current, occurred_at=runtime.observed_at()
        )
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/assist")
def assist_draft(
    draft_id: str,
    body: DraftAssist,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
) -> dict:
    draft = runtime.communications.repository.get(draft_id)
    if not draft:
        raise HTTPException(404, "Communication draft not found.")
    account = next(
        item for item in runtime.environment().accounts if item.id == draft.account_id
    )
    provider = get_ai_provider(AiConfig.from_settings(runtime.settings, actor_id=current.user_id, purpose="communication"))
    if not runtime.communications._can_manage(current, draft):
        raise HTTPException(
            403, "This draft is outside the current principal's permitted work."
        )
    if draft.version != body.expected_version:
        raise HTTPException(409, 'The saved draft changed. Refresh before requesting another proposal.')
    outcome = draft_governed_content(
        _drafting_request(
            account,
            body.instruction,
            subject=draft.subject,
            body=draft.body,
            evidence_ids=draft.evidence_ids,
            intelligence_facts=_intelligence_facts(runtime, draft.account_id, draft.evidence_ids),
        ),
        provider,
    )
    latest = runtime.communications.repository.get(draft_id)
    if latest is None or latest.version != draft.version:
        raise HTTPException(409, 'The saved draft changed while the proposal was prepared. No content was applied; refresh and compare.')
    return {"draft": draft, **_proposal_payload(outcome)}


@router.post("/assist")
def assist_new_draft(
    body: DraftProposal,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
) -> dict:
    account = next(
        (item for item in runtime.environment().accounts if item.id == body.account_id),
        None,
    )
    if not account:
        raise HTTPException(404, "Canonical Customer not found.")
    provider = get_ai_provider(AiConfig.from_settings(runtime.settings, actor_id=current.user_id, purpose="communication"))
    outcome = draft_governed_content(
        _drafting_request(
            account,
            body.instruction,
            subject=body.subject,
            body=body.body,
            evidence_ids=body.evidence_ids,
            intelligence_facts=_intelligence_facts(runtime, body.account_id, body.evidence_ids),
        ),
        provider,
    )
    return _proposal_payload(outcome)


@router.post("/{draft_id}/approval")
def approval(
    draft_id: str,
    body: ApprovalDecision,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.communications.decide(
            draft_id,
            body.decision,
            expected_version=body.expected_version,
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/preview")
def preview(
    draft_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.communications.preview(
            draft_id,
            principal=current,
            occurred_at=runtime.observed_at(),
            delivery=UnconfiguredDeliveryAdapter(),
        )
    except Exception as error:
        raise _error(error) from error


@router.post("/{draft_id}/send")
def send(
    draft_id: str,
    expected_version: int = Query(ge=1),
    confirmed: bool = False,
    idempotency_key: str = "",
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    if not idempotency_key:
        raise HTTPException(422, "An idempotency key is required.")
    try:
        return runtime.communications.send(
            draft_id,
            expected_version=expected_version,
            principal=current,
            occurred_at=runtime.observed_at(),
            confirmed=confirmed,
            idempotency_key=idempotency_key,
            delivery=UnconfiguredDeliveryAdapter(),
        )
    except Exception as error:
        raise _error(error) from error


@router.get("/{draft_id}/history")
def history(
    draft_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
) -> dict:
    try:
        return {"events": runtime.communications.history(draft_id, current)}
    except Exception as error:
        raise _error(error) from error
