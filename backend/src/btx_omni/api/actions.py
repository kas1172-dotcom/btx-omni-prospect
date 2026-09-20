from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import (
    ActionPriority,
    ActionStatus,
    ApprovalStatus,
    Principal,
    PrincipalRole,
)
from btx_omni.integrations.hubspot.contracts import (
    CrmAccountContext,
    CrmProviderState,
    SampleHubSpotAdapter,
)
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.work.crm_proposals import CrmProposalWorkflow
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    ActionNotFoundError,
)
from btx_omni.persistence.work_feedback import FeedbackConflict

router = APIRouter(prefix="/actions", tags=["actions"])


class CreateAction(BaseModel):
    account_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    owner_id: str | None = None
    priority: ActionPriority = ActionPriority.MEDIUM
    due_date: date | None = None
    evidence_ids: tuple[str, ...] = ()
    context_referents: tuple[tuple[str, str], ...] = ()
    approval_required: bool = False
    idempotency_key: str | None = None


class EditAction(BaseModel):
    account_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    owner_id: str | None = None
    priority: ActionPriority | None = None
    due_date: date | None = None
    expected_version: int | None = Field(default=None, ge=1)


class StatusChange(BaseModel):
    status: ActionStatus
    complete_open_subtasks: bool = False
    expected_version: int | None = Field(default=None, ge=1)


class ApprovalDecision(BaseModel):
    decision: ApprovalStatus
    comment: str | None = Field(default=None, max_length=2000)
    expected_version: int | None = Field(default=None, ge=1)


class ApprovalRequest(BaseModel):
    expected_version: int = Field(ge=1)


class SubtaskMutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    done: bool = False
    due_date: date | None = None
    owner_id: str | None = None
    removed: bool = False


class SuggestionReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[0-9a-f]{64}$')


class SuggestionConversion(SuggestionReview):
    owner_id: str | None = None
    due_date: date | None = None


class SuggestionFeedbackInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    reason: Literal['WRONG_ACCOUNT', 'SNOOZE', 'ALREADY_DONE', 'NOT_RELEVANT', 'UNDO']
    note: str = Field(default='', max_length=500)
    expected_feedback_id: str | None = Field(default=None, max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9._-]+$')
    snooze_until: datetime | None = None


class CrmPreviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class CrmDecisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal_id: str = Field(pattern=r'^crm-proposal-[0-9a-f]{64}$')
    decision: Literal['APPROVED', 'REJECTED']
    expected_decision_id: str | None = Field(default=None, pattern=r'^crm-decision-[0-9a-f]{64}$')


class CrmAttemptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal_id: str = Field(pattern=r'^crm-proposal-[0-9a-f]{64}$')
    expected_decision_id: str = Field(pattern=r'^crm-decision-[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9._-]+$')


def _crm_workflow(runtime):
    if runtime.settings.data_mode != 'SAMPLE':
        raise ActionConflictError('Only the local SAMPLE CRM workflow is authorized.')
    sample = runtime.environment()
    contexts = {}
    for company in sample.crm_companies:
        if company.account_id in contexts:
            raise ActionConflictError('Ambiguous CRM company mapping requires review.')
        contexts[company.account_id] = CrmAccountContext(company, (), (), (), (), CrmProviderState.AVAILABLE)
    return CrmProposalWorkflow(runtime.work, SampleHubSpotAdapter(contexts), commercial_revision=sample.commercial_revision)


def _handle(error: Exception) -> HTTPException:
    if isinstance(error, ActionNotFoundError):
        return HTTPException(404, "Action not found.")
    if isinstance(error, ActionForbiddenError):
        return HTTPException(403, str(error))
    if isinstance(error, ActionConflictError):
        return HTTPException(409, str(error))
    return HTTPException(400, str(error))


def _suggestions(runtime: PocRuntime, current: Principal) -> list[dict]:
    from btx_omni.modules.work.suggestions import project_suggestions

    sample = runtime.environment()
    alerts = CommercialAlertEngine().evaluate(
        sample.commercial_contexts,
        sample.quotes,
        observed_at=runtime.observed_at(),
        orders=sample.orders,
    )
    suggestions = project_suggestions(alerts, actions=runtime.work.repository.list(),
                                       visible_action_ids={item.id for item in runtime.work.list(current)},
                                       commercial_revision=sample.commercial_revision)
    feedback = runtime.work_feedback.current(current.user_id, tuple(item['id'] for item in suggestions), now=datetime.now(UTC),
                                            source_revisions={item['id']: item['revision'] for item in suggestions})
    return [{**item, 'feedback': feedback.get(item['id']),
             'dismissed': feedback[item['id']]['hidden'] if item['id'] in feedback else item['dismissed']}
            for item in suggestions]


@router.get("/principal")
def current_principal(current: Principal = Depends(principal)) -> Principal:
    return current


@router.get('/suggestion-feedback/history')
def suggestion_feedback_history(offset: int = 0, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return runtime.work_feedback.history(current.user_id, offset=offset)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


class UndoFeedbackReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=8, max_length=64)


@router.post('/suggestion-feedback/{receipt_id}/undo')
def undo_feedback_receipt(receipt_id: str, body: UndoFeedbackReceipt, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    original = runtime.work_feedback.receipt(current.user_id, receipt_id)
    if original is None:
        raise HTTPException(404, 'Feedback receipt not found in your scope.')
    try:
        receipt = runtime.work_feedback.append(user_id=current.user_id, suggestion_id=original['suggestion_id'],
                                              account_id=original['account_id'], reason='UNDO', note='', now=datetime.now(UTC),
                                              idempotency_key=body.idempotency_key, expected_feedback_id=receipt_id)
    except FeedbackConflict as error:
        raise HTTPException(409, str(error)) from error
    return {'receipt_id': receipt['id'], 'state': 'RESTORED', 'scope': 'CURRENT_USER_ONLY', 'external_write': False}


@router.get("")
def list_actions(
    runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)
) -> dict:
    return {
        "items": runtime.work.list(current),
        "suggestions": _suggestions(runtime, current),
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
    if body.account_id is not None and body.account_id not in {item.id for item in sample.accounts}:
        raise HTTPException(404, "Canonical Customer not found.")
    assessment_ids = [value for kind, value in body.context_referents if kind == "intelligence_assessment"]
    if assessment_ids:
        if len(assessment_ids) != 1 or not runtime.monitor.repository:
            raise HTTPException(409, "Choose one current Intelligence assessment for this proposal.")
        assessment = runtime.monitor.repository.intelligence_assessment_by_id(assessment_ids[0])
        if not assessment or assessment["account_id"] != body.account_id or not assessment["is_current"]:
            raise HTTPException(409, "The Intelligence assessment changed; refresh before creating the proposal.")
        supported = set(assessment["projection"].get("evidence_ids", ())) | {assessment["id"]}
        if not set(body.evidence_ids) <= supported:
            raise HTTPException(422, "Action evidence must come from the selected current Intelligence assessment.")
    federal_ids = [value for kind, value in body.context_referents if kind == "federal_assessment"]
    if federal_ids:
        if len(federal_ids) != 1 or not runtime.monitor.repository:
            raise HTTPException(409, "Choose one current federal assessment for this proposal.")
        federal = runtime.monitor.repository.federal_assessment_by_id(federal_ids[0])
        refs = dict(body.context_referents)
        if not federal or not federal["is_current"]:
            raise HTTPException(409, "The federal assessment changed; refresh before creating the proposal.")
        projection = federal["projection"]
        if refs.get("federal_opportunity") != federal["opportunity_id"] or refs.get("federal_assessment_version") != str(federal["version"]):
            raise HTTPException(409, "The federal opportunity context is incomplete or stale.")
        route = next((item for item in projection.get("routes", ()) if item.get("route_type") == refs.get("federal_route_type") and item.get("account_id") == body.account_id), None)
        if route is None:
            raise HTTPException(422, "The selected federal route does not support this organization.")
        partner = refs.get("strategic_partnership")
        if partner and (route.get("route_type") != "STRATEGIC_PARTNER" or partner != body.account_id):
            raise HTTPException(422, "The selected route does not support this strategic partnership.")
        supported = {federal["id"], *projection.get("evidence_references", ())}
        if not set(body.evidence_ids) <= supported:
            raise HTTPException(422, "Action evidence must come from the selected current federal assessment.")
        if body.title.strip() != route.get("governed_action"):
            raise HTTPException(422, "The proposal must preserve the governed federal validation step.")
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
            for item in _suggestions(runtime, current)
            if item["id"] == suggestion_id and not item["dismissed"]
        ),
        None,
    )
    if not suggestion:
        raise HTTPException(404, "Active Suggestion not found.")
    if suggestion['conversion_blocked']:
        raise HTTPException(409, 'Existing work requires authorized review before creating another Action.')
    if suggestion['converted_action_id']:
        return runtime.work.get(suggestion['converted_action_id'])
    if body.expected_revision != suggestion['revision']:
        raise HTTPException(409, 'Recommendation evidence changed; refresh and review it before creating an Action. Your draft can be retained.')
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
    body: SuggestionReview,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
) -> None:
    suggestion = next((item for item in _suggestions(runtime, current) if item['id'] == suggestion_id), None)
    if suggestion is None:
        raise HTTPException(404, "Suggestion not found.")
    if body.expected_revision != suggestion['revision']:
        raise HTTPException(409, 'Recommendation evidence changed; refresh before dismissing it.')
    feedback = suggestion.get('feedback')
    if feedback and feedback['reason'] == 'NOT_RELEVANT' and not feedback['source_changed']:
        return
    prior_id = feedback['id'] if feedback else None
    try:
        runtime.work_feedback.append(user_id=current.user_id, suggestion_id=suggestion_id, account_id=suggestion['account_id'],
                                     reason='NOT_RELEVANT', note='Personal relevance dismissal; no task status changed.', now=datetime.now(UTC),
                                     idempotency_key=sha256(f'{current.user_id}:{suggestion_id}:{prior_id}:dismiss'.encode()).hexdigest(),
                                     expected_feedback_id=prior_id, source_revision=body.expected_revision,
                                     current_source_revision=suggestion['revision'])
    except FeedbackConflict as error:
        raise HTTPException(409, str(error)) from error


@router.post('/suggestions/{suggestion_id}/feedback')
def record_suggestion_feedback(suggestion_id: str, body: SuggestionFeedbackInput,
                               runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    suggestion = next((item for item in _suggestions(runtime, current) if item['id'] == suggestion_id), None)
    if suggestion is None:
        raise HTTPException(404, 'Canonical suggestion not found.')
    now = datetime.now(UTC)
    try:
        receipt = runtime.work_feedback.append(user_id=current.user_id, suggestion_id=suggestion_id,
                                              account_id=suggestion['account_id'], now=now,
                                              source_revision=body.expected_revision, current_source_revision=suggestion['revision'],
                                              **body.model_dump(exclude={'expected_revision'}))
    except FeedbackConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {'receipt_id': receipt['id'], 'current': runtime.work_feedback.current(current.user_id, (suggestion_id,), now=now,
                                                                               source_revisions={suggestion_id: suggestion['revision']})[suggestion_id],
            'external_write': False, 'canonical_scores_changed': False, 'work_status_changed': False}


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
    if 'account_id' in body.model_fields_set:
        if body.account_id is not None and body.account_id not in {item.id for item in runtime.environment().accounts}:
            raise HTTPException(404, "Canonical Customer not found.")
        existing = get_action(action_id, runtime, current)
        if (existing.evidence_ids or existing.context_referents or existing.source_suggestion_id) and body.account_id != existing.account_id:
            raise HTTPException(409, "A sourced task must retain its evidence-linked customer.")
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
            action_id, body.status, principal=current, occurred_at=runtime.observed_at(), expected_version=body.expected_version,
            complete_open_subtasks=body.complete_open_subtasks,
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
            expected_version=body.expected_version,
            comment=body.comment,
        )
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/approval/request")
def request_approval(action_id: str, body: ApprovalRequest, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return runtime.work.request_approval(action_id, principal=current, occurred_at=runtime.observed_at(), expected_version=body.expected_version)
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/subtasks")
def add_subtask(action_id: str, body: SubtaskMutation, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    if not body.title:
        raise HTTPException(422, "Subtask title is required.")
    return mutate_subtask(action_id, None, body, runtime, current)


@router.patch("/{action_id}/subtasks/{subtask_id}")
def mutate_subtask(action_id: str, subtask_id: str, body: SubtaskMutation, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        changes = body.model_dump(exclude_unset=True, exclude={'expected_version', 'idempotency_key'})
        if 'title' in changes and changes['title'] is None:
            raise ValueError("Subtask title is required.")
        return runtime.work.change_subtask(action_id, subtask_id=subtask_id, principal=current, occurred_at=runtime.observed_at(),
                                           expected_version=body.expected_version, idempotency_key=body.idempotency_key, **changes)
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError, ValueError) as error:
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
    body: 'CrmPreviewInput',
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    try:
        return _crm_workflow(runtime).preview(action_id, expected_version=body.expected_version, principal=current, now=datetime.now(UTC))
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.get('/{action_id}/crm-proposals')
def crm_proposals(action_id: str, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return _crm_workflow(runtime).inspect(action_id, principal=current)
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.post('/{action_id}/crm-proposal-decision')
def crm_proposal_decision(action_id: str, body: CrmDecisionInput, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    try:
        return _crm_workflow(runtime).decide(action_id, **body.model_dump(), principal=current, now=datetime.now(UTC))
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error


@router.post("/{action_id}/crm-execute")
def crm_execute(
    action_id: str,
    body: 'CrmAttemptInput | None' = None,
    confirmed: bool = False,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    if not confirmed:
        raise HTTPException(
            409, "Explicit human confirmation is required before CRM execution."
        )
    if body is None:
        raise HTTPException(422, 'A saved proposal, current approval and retry key are required.')
    try:
        return _crm_workflow(runtime).execute_sample(action_id, **body.model_dump(), principal=current, now=datetime.now(UTC))
    except (ActionNotFoundError, ActionForbiddenError, ActionConflictError) as error:
        raise _handle(error) from error
