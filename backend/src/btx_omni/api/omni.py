from dataclasses import replace
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.ai.config import AiConfig
from btx_omni.ai.registry import get_ai_provider
from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.core.release import build_identity
from btx_omni.domain.work import Principal
from btx_omni.modules.assistant.market_context import selected_market_context
from btx_omni.modules.assistant.service import OmniService
from btx_omni.persistence.omni_runs import answer_receipt

router = APIRouter(prefix="/omni", tags=["omni"])


class OmniSurface(StrEnum):
    TODAY = "TODAY"
    ACCOUNTS = "ACCOUNTS"
    ACCOUNT_DETAIL = "ACCOUNT_DETAIL"
    INTELLIGENCE = "INTELLIGENCE"
    MAP = "MAP"
    ACTIONS = "ACTIONS"
    COMMUNICATIONS = "COMMUNICATIONS"
    SETTINGS = "SETTINGS"
    MONITOR = "MONITOR"


class OmniConversationReferent(BaseModel):
    """Bounded canonical continuation state; never derived from assistant prose."""

    model_config = ConfigDict(extra="forbid")
    account_id: str | None = None
    event_id: str | None = None
    opportunity_id: str | None = Field(default=None, max_length=300)
    assessment_id: str | None = None
    assessment_version: int | None = Field(default=None, ge=1)
    facility_id: str | None = None
    action_id: str | None = None
    comparison_account_ids: list[str] = Field(default_factory=list, max_length=2)
    relationship_account_ids: list[str] = Field(default_factory=list, max_length=2)
    route: str | None = Field(default=None, max_length=48)


class OmniRelationshipSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: str = Field(max_length=64)
    target_ids: list[Annotated[str, Field(min_length=1, max_length=280)]] = Field(min_length=1, max_length=25)
    mode: Literal["commercial_fit", "cross_account_experience", "contact_candidates", "documented_access"]
    as_of: date
    depth: int = Field(ge=1, le=6)
    path_id: str = Field(max_length=100)
    graph_revision: str = Field(max_length=64)
    source_component_id: str | None = Field(default=None, max_length=220)
    target_component_id: str | None = Field(default=None, max_length=220)


class OmniAssessmentSelection(BaseModel):
    """References one server-owned persisted intelligence assessment."""

    model_config = ConfigDict(extra="forbid")
    assessment_id: str = Field(min_length=1, max_length=64)
    assessment_version: int = Field(ge=1)
    event_id: str = Field(min_length=1, max_length=160)
    account_id: str = Field(min_length=1, max_length=64)


class OmniFederalSelection(BaseModel):
    """References one current server-owned federal assessment and route."""

    model_config = ConfigDict(extra="forbid")
    opportunity_id: str = Field(min_length=1, max_length=300)
    assessment_id: str = Field(min_length=1, max_length=64)
    assessment_version: int = Field(ge=1)
    route_type: Literal["DIRECT_BTX", "CUSTOMER_EXPANSION", "STRATEGIC_PARTNER", "NEW_PROSPECT", "MARKET_WATCH"]
    account_id: str | None = Field(default=None, max_length=64)
    partnership_id: str | None = Field(default=None, max_length=64)


class OmniCommercialSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=64)
    opportunity_id: str = Field(min_length=1, max_length=220)
    revision: str = Field(min_length=1, max_length=128)


class OmniContext(BaseModel):
    """Bounded passive product context; distinct from the user's explicit scope."""

    model_config = ConfigDict(extra="forbid")
    surface: OmniSurface | None = None
    # account_id is explicit request scope; selected is current UI; session is conversation continuity.
    session_account_id: str | None = None
    selected_account_id: str | None = None
    selected_event_id: str | None = None
    selected_assessment: OmniAssessmentSelection | None = None
    selected_federal_opportunity: OmniFederalSelection | None = None
    selected_commercial_opportunity: OmniCommercialSelection | None = None
    selected_facility_id: str | None = None
    selected_program_id: str | None = None
    selected_action_id: str | None = None
    active_filters: dict[str, str | list[str]] = Field(default_factory=dict, max_length=12)
    visible_record_ids: list[str] = Field(default_factory=list, max_length=50)
    prior_turns: str | None = Field(default=None, max_length=1600)
    conversation_referent: OmniConversationReferent | None = None
    relationship_selection: OmniRelationshipSelection | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_legacy_surface(cls, value: str | None) -> str | None:
        return value.upper() if isinstance(value, str) else value

    @field_validator("active_filters")
    @classmethod
    def bound_filters(cls, value: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
        for key, item in value.items():
            if len(key) > 80 or (isinstance(item, str) and len(item) > 160) or (isinstance(item, list) and (len(item) > 12 or any(len(entry) > 160 for entry in item))):
                raise ValueError("active_filters exceeds bounded context limits")
        return value


class OmniQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str | None = Field(default=None, max_length=64)
    question: str = Field(min_length=1, max_length=4000)
    context: OmniContext | None = None


@router.post("")
def omni(
    body: OmniQuestion,
    response: Response,
    runtime: PocRuntime = Depends(get_runtime),
    current: Principal = Depends(principal),
):
    from btx_omni.monitor.documents import document_evidence

    def selected_public_evidence(event_id: str, account_id: str | None):
        repository = runtime.monitor.repository
        record = repository.event_document(event_id, include_research=True) if repository else None
        if record is None or (account_id is not None and account_id not in record["canonical_account_ids"]):
            return ()
        return document_evidence(record)

    def selected_market_read(filters):
        try:
            return selected_market_context(runtime.markets, filters, runtime.environment())
        except SQLAlchemyError:
            raise ValueError('Canonical market storage is unavailable.') from None

    response.headers['Cache-Control'] = 'private, no-store'
    try:
        run_id = runtime.omni_runs.start(actor_id=current.user_id, request=body.model_dump(mode='json'), now=datetime.now(UTC))
    except SQLAlchemyError:
        raise HTTPException(503, 'Omni run recording is unavailable. No model call was started; retry later.') from None
    try:
        federal_context = None
        if body.context and body.context.selected_federal_opportunity:
            selection = body.context.selected_federal_opportunity
            repository = runtime.monitor.repository
            row = repository.federal_assessment_by_id(selection.assessment_id, version=selection.assessment_version) if repository else None
            if not row or not row["is_current"] or row["opportunity_id"] != selection.opportunity_id:
                raise ValueError("Selected federal assessment is stale or unavailable.")
            projection = row["projection"]
            route = next((item for item in projection.get("routes", ()) if item.get("route_type") == selection.route_type and item.get("account_id") == selection.account_id), None)
            if route is None:
                raise ValueError("Selected federal route is unavailable.")
            if selection.partnership_id and (selection.partnership_id != selection.account_id or route.get("route_type") != "STRATEGIC_PARTNER"):
                raise ValueError("Selected partnership route is unavailable.")
            federal_context = {
                **projection,
                "assessment_id": row["id"],
                "assessment_version": row["version"],
                "selected_route": route,
                "selected_account_id": selection.account_id,
                "selected_partnership_id": selection.partnership_id,
            }
        provider = get_ai_provider(AiConfig.from_settings(runtime.settings, actor_id=current.user_id, purpose="omni"))
        answer = OmniService(provider).answer(
            runtime.environment(),
            account_id=body.account_id,
            question=body.question,
            observed_at=runtime.observed_at(),
            context=(body.context.model_dump(exclude_none=True) if body.context else {}),
            intelligence_events=intelligence_signals(runtime),
            work_items=runtime.work.list(current),
            memory_reader=lambda account_id: runtime.memory.list(current.user_id, now=datetime.now(UTC),
                                                                 account_id=account_id, for_context=True),
            public_evidence_reader=selected_public_evidence,
            market_reader=selected_market_read,
            federal_context=federal_context,
        )
        answer = replace(answer, provider_usage=tuple(getattr(provider, "usage_log", ())), run_id=run_id)
        runtime.omni_runs.finish(run_id, actor_id=current.user_id,
            result=answer_receipt(answer, build=build_identity(runtime.settings)), now=datetime.now(UTC))
    except (SQLAlchemyError, RuntimeError, ValueError, TimeoutError, KeyError, TypeError) as error:
        # Store only a controlled failure class. No DSN, SDK error, input, or private
        # reasoning belongs in operational failure receipts.
        try:
            runtime.omni_runs.finish(run_id, actor_id=current.user_id, result={'failure_class': type(error).__name__},
                                     now=datetime.now(UTC), failed=True)
        except (SQLAlchemyError, ValueError):
            pass  # RUNNING becomes explicitly outcome-unknown when inspected.
        raise HTTPException(503, f'Omni could not complete a recorded answer. Run reference: {run_id}. No external action was executed.') from None
    return answer


@router.get('/runs/{run_id}')
def omni_run(run_id: str, response: Response, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    from btx_omni.persistence.omni_conversations import owner_key
    response.headers['Cache-Control'] = 'private, no-store'
    if len(run_id) != 36:
        raise HTTPException(404, 'Omni run unavailable.')
    try:
        result = runtime.omni_runs.get(run_id, actor_id=owner_key(current), now=datetime.now(UTC))
        if result is None:
            result = runtime.omni_runs.get(run_id, actor_id=current.user_id, now=datetime.now(UTC))
    except SQLAlchemyError:
        raise HTTPException(503, 'Omni run recording is unavailable.') from None
    if result is None:
        raise HTTPException(404, 'Omni run unavailable.')
    return result


@router.post('/chat')
def chat(body: OmniQuestion, response: Response, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    """V2 entry point; the original endpoint remains a compatibility read path."""
    response.headers['Cache-Control'] = 'private, no-store'
    return answer_chat(body, runtime, current)


def answer_chat(body, runtime, current, *, progress=None, canceled=None):
    from btx_omni.modules.assistant.chat_agent import ChatAgent, ChatLimits
    from btx_omni.modules.assistant.chat_tools import ChatTools
    from btx_omni.modules.federal_procurement import federal_assessments_for_account
    from btx_omni.persistence.omni_conversations import owner_key

    config = AiConfig.from_settings(runtime.settings, actor_id=current.user_id, purpose='omni-chat-v2')
    config = replace(config, model=runtime.settings.omni_chat_model or config.model,
                     daily_actor_limit=min(config.daily_actor_limit, runtime.settings.omni_chat_daily_calls))
    provider = get_ai_provider(config)
    context = body.context.model_dump(exclude_none=True) if body.context else {}
    tools = ChatTools(runtime.environment(), current, observed_at=runtime.observed_at(), context=context,
                      provider=provider, web_enabled=runtime.settings.web_search_enabled,
                      general_enabled=runtime.settings.general_knowledge_enabled,
                      events=intelligence_signals(runtime), work=runtime.work.list(current),
                      federal_reader=lambda aid: {'assessments': federal_assessments_for_account(runtime, aid)} if aid else {'status': 'unavailable', 'message': 'Select an organization to inspect its federal opportunities.'})
    try:
        run_id = runtime.omni_runs.start(actor_id=owner_key(current), request=body.model_dump(mode='json'), now=datetime.now(UTC))
    except SQLAlchemyError:
        raise HTTPException(503, "Omni's private history is unavailable. Please try again.") from None
    answer = ChatAgent(provider, tools, progress=progress, canceled=canceled, limits=ChatLimits(steps=runtime.settings.omni_chat_steps,
                                                        output_tokens=runtime.settings.omni_chat_output_tokens)).answer(
        body.question, account_id=body.account_id, recent_turns=OmniService._recent_turns(context.get('prior_turns')))
    answer = replace(answer, run_id=run_id, provider_usage=tuple(getattr(provider, 'usage_log', ())))
    try:
        runtime.omni_runs.finish(run_id, actor_id=owner_key(current), result=answer_receipt(answer, build=build_identity(runtime.settings)), now=datetime.now(UTC))
    except SQLAlchemyError:
        raise HTTPException(503, "Omni couldn't save this answer. Please try again.") from None
    return answer
