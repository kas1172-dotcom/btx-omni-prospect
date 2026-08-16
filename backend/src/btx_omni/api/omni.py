from fastapi import APIRouter, Depends
from pydantic import BaseModel

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.assistant.orchestration import OmniOrchestrator

router = APIRouter(prefix="/omni", tags=["omni"])


class OmniQuestion(BaseModel):
    account_id: str
    question: str


@router.post("")
def omni(body: OmniQuestion, runtime: PocRuntime = Depends(get_runtime)):
    return OmniOrchestrator().answer(runtime.environment(), account_id=body.account_id, question=body.question, observed_at=runtime.observed_at())
