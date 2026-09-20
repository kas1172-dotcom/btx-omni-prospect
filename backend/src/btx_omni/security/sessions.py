"""Opaque, short-lived hosted POC sessions; production identity remains external."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from hashlib import sha256
from secrets import token_urlsafe
from threading import Lock

from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole


def server_principal(settings: Settings, user_id: str, display_name: str, role: PrincipalRole) -> Principal:
    # Future identity-provider mapping seam: tenant authority must remain server-side.
    return Principal(user_id, display_name, role, settings.omni_tenant_id)


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
        return bool(self.settings.user_access_code_hashes) or all(
            (
                self.settings.action_salesperson_token,
                self.settings.action_manager_token,
            )
        ) and not (
            self.settings.action_salesperson_token == "development-salesperson"
            or self.settings.action_manager_token == "development-manager"
        )

    def exchange(self, access_code: str, *, now: datetime | None = None) -> Session | None:
        principal = None
        digest = sha256(access_code.encode("utf-8")).hexdigest()
        # Scan every configured hash; client identity fields are never consulted.
        matches = [user for user, expected in self.settings.user_access_code_hashes.items()
                   if compare_digest(digest, expected)]
        seller = compare_digest(access_code.encode(), self.settings.action_salesperson_token.encode())
        manager = compare_digest(access_code.encode(), self.settings.action_manager_token.encode())
        if (matches and (seller or manager)) or len(matches) > 1 or (seller and manager):
            return None  # Ambiguous credentials must never choose an identity.
        if matches:
            principal = server_principal(self.settings, matches[0], "Configured user", PrincipalRole.SALESPERSON)
        elif seller and (self.settings.environment == "development" or access_code != "development-salesperson"):
            principal = server_principal(self.settings, "shared-access", "POC Salesperson", PrincipalRole.SALESPERSON)
        elif manager and (self.settings.environment == "development" or access_code != "development-manager"):
            principal = server_principal(self.settings, "shared-access-manager", "POC Manager", PrincipalRole.MANAGER)
        if principal is None:
            return None
        return self._create(principal, now=now)

    def create_sample_demo_salesperson(self, *, now: datetime | None = None) -> Session | None:
        """Issue the normal hosted session only for the explicit SAMPLE demo flag."""
        if not self.settings.hosted_demo_access_bypass_enabled:
            return None
        return self._create(
            server_principal(self.settings, "shared-access", "POC Salesperson", PrincipalRole.SALESPERSON),
            now=now,
        )

    def _create(self, principal: Principal, *, now: datetime | None = None) -> Session:
        clock = now or datetime.now(UTC)
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
