from fastapi import APIRouter, Depends
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.assistant.orchestration import OmniOrchestrator

router = APIRouter(prefix="/omni", tags=["omni"])


class OmniSurface(StrEnum):
    TODAY = "TODAY"
    ACCOUNTS = "ACCOUNTS"
    ACCOUNT_DETAIL = "ACCOUNT_DETAIL"
    INTELLIGENCE = "INTELLIGENCE"
    MAP = "MAP"
    ACTIONS = "ACTIONS"


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
    account_id: str | None = None
    question: str
    context: OmniContext | None = None


@router.post("")
def omni(body: OmniQuestion, runtime: PocRuntime = Depends(get_runtime)):
    return OmniOrchestrator().answer(runtime.environment(), account_id=body.account_id, question=body.question, observed_at=runtime.observed_at(), context=(body.context.model_dump(exclude_none=True) if body.context else {}))
