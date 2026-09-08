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


class OmniContext(BaseModel):
    """Bounded passive product context; distinct from the user's explicit scope."""

    model_config = ConfigDict(extra="forbid")
    surface: OmniSurface | None = None
    # account_id is explicit request scope; selected is current UI; session is conversation continuity.
    session_account_id: str | None = None
    selected_account_id: str | None = None
    selected_event_id: str | None = None
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
    response.headers['Cache-Control'] = 'private, no-store'
    if len(run_id) != 36:
        raise HTTPException(404, 'Omni run unavailable.')
    try:
        result = runtime.omni_runs.get(run_id, actor_id=current.user_id, now=datetime.now(UTC))
    except SQLAlchemyError:
        raise HTTPException(503, 'Omni run recording is unavailable.') from None
    if result is None:
        raise HTTPException(404, 'Omni run unavailable.')
    return result
