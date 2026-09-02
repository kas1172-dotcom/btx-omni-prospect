from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.domain.work import Principal, PrincipalRole

router = APIRouter(prefix="/session", tags=["session"])


class SignIn(BaseModel):
    access_code: str = Field(min_length=1, max_length=500)


def _session_payload(session) -> dict:
    return {
        "authenticated": True,
        "principal": session.principal,
        "expires_at": session.expires_at,
        "csrf_token": session.csrf_token,
        "auth_mode": "HOSTED_POC_SESSION",
    }


def principal(
    request: Request,
    runtime: PocRuntime = Depends(get_runtime),
    development_token: str | None = Header(
        default=None, alias="X-BTX-Principal-Token"
    ),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Principal:
    if runtime.settings.environment == "development" and development_token is None:
        return Principal(
            "seller-1", "Development Salesperson", PrincipalRole.SALESPERSON
        )
    if runtime.settings.environment == "development" and development_token:
        if development_token == runtime.settings.action_salesperson_token:
            return Principal(
                "seller-1", "Development Salesperson", PrincipalRole.SALESPERSON
            )
        if development_token == runtime.settings.action_manager_token:
            return Principal(
                "manager-1", "Development Manager", PrincipalRole.MANAGER
            )
    session = runtime.sessions.get(
        request.cookies.get(runtime.settings.session_cookie_name)
    )
    if session is None:
        raise HTTPException(401, "A valid hosted session is required.")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
        not csrf_token or csrf_token != session.csrf_token
    ):
        raise HTTPException(403, "CSRF validation failed.")
    return session.principal


@router.post("/sign-in")
def sign_in(
    body: SignIn,
    response: Response,
    runtime: PocRuntime = Depends(get_runtime),
) -> dict:
    if (
        runtime.settings.environment != "development"
        and not runtime.sessions.production_configured
    ):
        raise HTTPException(503, "Hosted session credentials are not configured.")
    session = runtime.sessions.exchange(body.access_code)
    if session is None:
        raise HTTPException(401, "The access code is invalid.")
    production = runtime.settings.environment != "development"
    response.set_cookie(
        runtime.settings.session_cookie_name,
        session.id,
        max_age=max(60, runtime.settings.session_ttl_seconds),
        secure=production,
        httponly=True,
        samesite="none" if production else "lax",
        path=runtime.settings.api_prefix,
    )
    return _session_payload(session)


@router.get("")
def session_status(
    request: Request,
    runtime: PocRuntime = Depends(get_runtime),
) -> dict:
    session = runtime.sessions.get(
        request.cookies.get(runtime.settings.session_cookie_name)
    )
    if session is None:
        raise HTTPException(401, "A valid hosted session is required.")
    return _session_payload(session)


@router.post("/sign-out")
def sign_out(
    request: Request,
    response: Response,
    runtime: PocRuntime = Depends(get_runtime),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict:
    session_id = request.cookies.get(runtime.settings.session_cookie_name)
    session = runtime.sessions.get(session_id, now=datetime.now(UTC))
    if session is None:
        raise HTTPException(401, "A valid hosted session is required.")
    if not csrf_token or csrf_token != session.csrf_token:
        raise HTTPException(403, "CSRF validation failed.")
    runtime.sessions.revoke(session_id)
    response.delete_cookie(
        runtime.settings.session_cookie_name,
        path=runtime.settings.api_prefix,
        secure=runtime.settings.environment != "development",
        httponly=True,
        samesite="none" if runtime.settings.environment != "development" else "lax",
    )
    return {"authenticated": False}
