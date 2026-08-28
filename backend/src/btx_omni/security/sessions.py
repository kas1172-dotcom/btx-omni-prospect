"""Opaque, short-lived hosted POC sessions; production identity remains external."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from secrets import token_urlsafe
from threading import Lock

from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole


@dataclass(frozen=True)
class Session:
    id: str
    csrf_token: str
    principal: Principal
    expires_at: datetime


class SessionStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    @property
    def production_configured(self) -> bool:
        return all(
            (
                self.settings.action_salesperson_token,
                self.settings.action_manager_token,
            )
        ) and not (
            self.settings.action_salesperson_token == "development-salesperson"
            or self.settings.action_manager_token == "development-manager"
        )

    def exchange(self, access_code: str, *, now: datetime | None = None) -> Session | None:
        clock = now or datetime.now(UTC)
        principal = None
        if compare_digest(access_code, self.settings.action_salesperson_token):
            principal = Principal("seller-1", "POC Salesperson", PrincipalRole.SALESPERSON)
        elif compare_digest(access_code, self.settings.action_manager_token):
            principal = Principal("manager-1", "POC Manager", PrincipalRole.MANAGER)
        if principal is None:
            return None
        session = Session(
            token_urlsafe(32),
            token_urlsafe(24),
            principal,
            clock + timedelta(seconds=max(60, self.settings.session_ttl_seconds)),
        )
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str | None, *, now: datetime | None = None) -> Session | None:
        if not session_id:
            return None
        clock = now or datetime.now(UTC)
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.expires_at > clock:
                return session
            self._sessions.pop(session_id, None)
        return None

    def revoke(self, session_id: str | None) -> None:
        if session_id:
            with self._lock:
                self._sessions.pop(session_id, None)
