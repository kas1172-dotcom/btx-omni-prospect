from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal
from btx_omni.persistence.omni_memory import MemoryConflict

router = APIRouter(prefix="/omni/memories", tags=["omni"])


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str | None = Field(default=None, max_length=64)
    kind: Literal["ANSWER_STYLE", "WORK_PREFERENCE"]
    content: str = Field(min_length=1, max_length=600)
    ttl_days: int = Field(default=90, ge=1, le=365)


class MemoryEdit(MemoryInput):
    expected_version: int = Field(ge=1)


class MemoryCreate(MemoryInput):
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9._-]+$')


class MemoryDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


@router.get("")
def memories(response: Response, actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    response.headers["Cache-Control"] = "private, no-store"
    return {"items": runtime.memory.list(actor.user_id, now=datetime.now(UTC)),
            "scope": "Only your preferences; managers cannot read another user's memories.",
            "authority": "Preferences never establish public facts, change deterministic scores or authorize execution."}


def _save(body: MemoryInput, actor: Principal, runtime: PocRuntime, memory_id=None):
    if body.account_id and body.account_id not in {a.id for a in runtime.environment().accounts}:
        raise HTTPException(404, "Canonical account not found.")
    try:
        return runtime.memory.save(user_id=actor.user_id, now=datetime.now(UTC), memory_id=memory_id, **body.model_dump())
    except MemoryConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("")
def create_memory(body: MemoryCreate, response: Response, actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    response.headers["Cache-Control"] = "private, no-store"
    return _save(body, actor, runtime)


@router.patch("/{memory_id}")
def edit_memory(memory_id: str, body: MemoryEdit, response: Response, actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    response.headers["Cache-Control"] = "private, no-store"
    return _save(body, actor, runtime, memory_id)


@router.post("/{memory_id}/delete")
def delete_memory(memory_id: str, body: MemoryDelete, response: Response, actor: Principal = Depends(principal), runtime: PocRuntime = Depends(get_runtime)):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        runtime.memory.delete(memory_id, user_id=actor.user_id, expected_version=body.expected_version)
    except MemoryConflict as error:
        raise HTTPException(409, str(error)) from error
    return {"deleted": True, "id": memory_id}
