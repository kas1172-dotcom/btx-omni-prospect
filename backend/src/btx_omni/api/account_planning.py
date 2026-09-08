from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.account_planning import AccountPlanningConflict

router = APIRouter(prefix="/planning", tags=["account-planning"])


class PartnershipInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    designated: bool
    reason: str = Field(min_length=10, max_length=1000)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


class ShortlistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=100)
    kind: Literal["GROWTH", "RESEARCH"]
    objective: str = Field(min_length=10, max_length=1000)
    target_date: date | None = None
    active: bool = True
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


def _account(runtime: PocRuntime, account_id: str):
    account = next((item for item in runtime.environment().accounts if item.id == account_id), None)
    if account is None:
        raise HTTPException(404, "Canonical Customer or Prospect not found.")
    return account


@router.get("")
def planning(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    return {**runtime.account_planning.view(current.user_id),
            "can_manage_partnerships": current.role is PrincipalRole.MANAGER}


@router.post("/partnerships/{account_id}")
def designate_partnership(account_id: str, body: PartnershipInput,
                          runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    if current.role is not PrincipalRole.MANAGER:
        raise HTTPException(403, "Manager permission is required to change a strategic-partnership designation.")
    _account(runtime, account_id)
    try:
        return runtime.account_planning.designate(
            account_id=account_id, designated=body.designated, reason=body.reason.strip(),
            actor_id=current.user_id, expected_version=body.expected_version,
            idempotency_key=body.idempotency_key, now=datetime.now(UTC),
        )
    except AccountPlanningConflict as error:
        raise HTTPException(409, str(error)) from error


@router.post("/shortlist")
def save_shortlist(body: ShortlistInput, runtime: PocRuntime = Depends(get_runtime),
                   current: Principal = Depends(principal)):
    _account(runtime, body.account_id)
    if body.active and body.target_date and body.target_date < datetime.now(UTC).date():
        raise HTTPException(422, "An active pursuit target date cannot be in the past.")
    try:
        return runtime.account_planning.save_shortlist(
            user_id=current.user_id, account_id=body.account_id, kind=body.kind,
            objective=body.objective.strip(), target_date=body.target_date.isoformat() if body.target_date else None,
            active=body.active, expected_version=body.expected_version,
            idempotency_key=body.idempotency_key, now=datetime.now(UTC),
        )
    except AccountPlanningConflict as error:
        raise HTTPException(409, str(error)) from error
