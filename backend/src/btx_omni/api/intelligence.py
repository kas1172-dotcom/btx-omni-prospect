from fastapi import APIRouter, Depends, HTTPException, Response

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("")
def intelligence(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    signals = intelligence_signals(runtime)
    return {"signals": signals, "provenance": "source URL and evidence state are retained"}


@router.get("/{event_id}/evidence")
def intelligence_evidence(event_id: str, response: Response, actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    repository = runtime.monitor.repository
    if repository is None:
        raise HTTPException(503, "Persistent public evidence is not configured.")
    document = repository.event_document(event_id, include_research=True)
    if document is None:
        raise HTTPException(404, "No persisted public source for the selected event.")
    assessments = []
    for account_id in document.get("canonical_account_ids", ()) or (None,):
        history = repository.intelligence_assessment_history(event_id, account_id=account_id)
        if history:
            assessments.append({"account_id": account_id, "current": history[0],
                                "history": history, "version_count": len(history)})
    document["intelligence_assessments"] = assessments
    return document
