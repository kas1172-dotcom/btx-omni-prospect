from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.work import (
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
    Principal,
    PrincipalRole,
)
from btx_omni.integrations.hubspot.contracts import SampleHubSpotAdapter
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    ActionNotFoundError,
)

router = APIRouter(prefix="/actions", tags=["actions"])


class CreateAction(BaseModel):
    account_id: str
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    owner_id: str | None = None
    priority: ActionPriority = ActionPriority.MEDIUM
    due_date: date | None = None
    evidence_ids: tuple[str, ...] = ()
    approval_required: bool = False
    idempotency_key: str | None = None


class EditAction(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    owner_id: str | None = None
    priority: ActionPriority | None = None
    due_date: date | None = None


class StatusChange(BaseModel):
    status: ActionStatus


class ApprovalDecision(BaseModel):
    decision: ApprovalStatus


class SuggestionConversion(BaseModel):
    owner_id: str | None = None
    due_date: date | None = None


def principal(
    runtime: PocRuntime = Depends(get_runtime),
    token: str | None = Header(default=None, alias="X-BTX-Principal-Token"),
) -> Principal:
    if token == runtime.settings.action_salesperson_token:
        return Principal(
            "seller-1", "Development Salesperson", PrincipalRole.SALESPERSON
        )
    if token == runtime.settings.action_manager_token:
        return Principal("manager-1", "Development Manager", PrincipalRole.MANAGER)
    raise HTTPException(401, "A configured development principal token is required.")


def _handle(error: Exception) -> HTTPException:
    if isinstance(error, ActionNotFoundError):
        return HTTPException(404, "Action not found.")
    if isinstance(error, ActionForbiddenError):
        return HTTPException(403, str(error))
    if isinstance(error, ActionConflictError):
        return HTTPException(409, str(error))
    return HTTPException(400, str(error))


def _suggestions(runtime: PocRuntime) -> list[dict]:
    sample = runtime.environment()
    dismissed = runtime.work.dismissed_suggestions()
    alerts = CommercialAlertEngine().evaluate(
        sample.commercial_contexts,
        sample.quotes,
        observed_at=runtime.observed_at(),
        orders=sample.orders,
    )
    return [
        {
            "id": suggestion_id,
            "account_id": item.account_id,
            "title": item.recommended_action,
            "rationale": item.trigger_reason,
            "priority": item.severity,
            "evidence_ids": item.evidence_ids,
            "source": "SAMPLE_COMMERCIAL_ALERT",
            "observed_at": item.observed_at,
            "dismissed": suggestion_id in dismissed,
            "converted_action_id": (
                converted.id
                if (converted := runtime.work.repository.by_suggestion(suggestion_id))
                else None
            ),
        }
        for index, item in enumerate(alerts)
        if (suggestion_id := f"{item.id}:{index}")
    ]


@router.get("/principal")
def current_principal(current: Principal = Depends(principal)) -> Principal:
    return current


@router.get("")
def list_actions(
    runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)
) -> dict:
    return {
        "items": runtime.work.list(current),
        "suggestions": _suggestions(runtime),
        "principal": current,
        "persistence": "DURABLE_DATABASE",
        "warning": "Actions and structured history are stored in the application database. External CRM operations remain simulated and governed.",
    }


@router.post("")
def create(
    body: CreateAction,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    sample = runtime.environment()
    if body.account_id not in {item.id for item in sample.accounts}:
        raise HTTPException(404, "Canonical Customer not found.")
    try:
        return runtime.work.create(
            **body.model_dump(), principal=current, occurred_at=runtime.observed_at()
        )
    except (ActionForbiddenError, ActionConflictError, ValueError) as error:
        raise _handle(error) from error


@router.post("/suggestions/{suggestion_id}/convert")
def convert_suggestion(
    suggestion_id: str,
    body: SuggestionConversion,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    suggestion = next(
        (
            item
            for item in _suggestions(runtime)
            if item["id"] == suggestion_id and not item["dismissed"]
        ),
        None,
    )
    if not suggestion:
        raise HTTPException(404, "Active Suggestion not found.")
    try:
        return runtime.work.create(
            account_id=suggestion["account_id"],
            title=suggestion["title"],
            description=suggestion["rationale"],
            evidence_ids=tuple(suggestion["evidence_ids"]),
            source_suggestion_id=suggestion_id,
            owner_id=body.owner_id,
            due_date=body.due_date,
            priority=ActionPriority(suggestion["priority"]),
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except (ActionForbiddenError, ActionConflictError, ValueError) as error:
        raise _handle(error) from error


@router.post("/suggestions/{suggestion_id}/dismiss", status_code=204)
def dismiss_suggestion(
    suggestion_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
) -> None:
    if not any(item["id"] == suggestion_id for item in _suggestions(runtime)):
        raise HTTPException(404, "Suggestion not found.")
    runtime.work.dismiss_suggestion(
        suggestion_id, principal=current, occurred_at=runtime.observed_at()
    )


@router.get("/{action_id}")
def get_action(
    action_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        action = runtime.work.get(action_id)
        if (
            current.role is PrincipalRole.SALESPERSON
            and action not in runtime.work.list(current)
        ):
            raise ActionForbiddenError(
                "This Action is outside the current principal's permitted work."
            )
        return action
    except (ActionNotFoundError, ActionForbiddenError) as error:
        raise _handle(error) from error


@router.patch("/{action_id}")
def edit_action(
    action_id: str,
    body: EditAction,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.work.edit(
            action_id,
            principal=current,
            occurred_at=runtime.observed_at(),
            **body.model_dump(exclude_unset=True),
        )
    except (
        ActionNotFoundError,
        ActionForbiddenError,
        ActionConflictError,
        ValueError,
    ) as error:
        raise _handle(error) from error


@router.post("/{action_id}/status")
def change_status(
    action_id: str,
    body: StatusChange,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.work.transition(
            action_id, body.status, principal=current, occurred_at=runtime.observed_at()
        )
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/approval")
def decide_approval(
    action_id: str,
    body: ApprovalDecision,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.work.decide_approval(
            action_id,
            body.decision,
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.get("/{action_id}/history")
def history(
    action_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        get_action(action_id, runtime, current)
        return {"events": runtime.work.audit(action_id)}
    except (ActionNotFoundError, ActionForbiddenError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/crm-preview")
def crm_preview(
    action_id: str,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return runtime.work.preview_crm_action(
            action_id,
            SampleHubSpotAdapter({}),
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except (ActionNotFoundError, ActionForbiddenError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/crm-execute")
def crm_execute(
    action_id: str,
    confirmed: bool = False,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    if not confirmed:
        raise HTTPException(
            409, "Explicit human confirmation is required before CRM execution."
        )
    try:
        return runtime.work.confirm_and_execute_crm_action(
            action_id,
            SampleHubSpotAdapter({}),
            principal=current,
            occurred_at=runtime.observed_at(),
        )
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error
