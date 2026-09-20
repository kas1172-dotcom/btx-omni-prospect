from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

import btx_omni.app as app_module
from btx_omni.core.config import Settings
from btx_omni.security.sessions import SessionStore


def _production_app(monkeypatch, **overrides) -> TestClient:
    settings = Settings(
        _env_file=None,
        environment="production",
        frontend_origins="https://btx-omni-prospect.vercel.app",
        action_salesperson_token="hosted-seller-access",
        action_manager_token="hosted-manager-access",
        **overrides,
    )
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    return TestClient(app_module.create_app(), base_url="https://backend.test")


def _sign_in(client: TestClient, code: str) -> dict:
    response = client.post("/api/session/sign-in", json={"access_code": code})
    assert response.status_code == 200
    return response.json()


def test_production_requires_session_and_has_no_development_header_fallback(
    monkeypatch,
) -> None:
    client = _production_app(monkeypatch)
    assert client.get("/api/actions").status_code == 401
    for path in ("/api/accounts", "/api/accounts/boeing", "/api/map", "/api/today", "/api/intelligence",
                 "/api/accounts/kla/workbook-fields", "/api/accounts/kla/workbook-fields/" + "a" * 64):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"
    assert client.get("/api/health").status_code == 200
    assert (
        client.get(
            "/api/actions",
            headers={"X-BTX-Principal-Token": "development-salesperson"},
        ).status_code
        == 401
    )


def test_salesperson_and_manager_sessions_preserve_role_policy(monkeypatch) -> None:
    manager_client = _production_app(monkeypatch)
    manager = _sign_in(manager_client, "hosted-manager-access")
    assert manager["principal"]["role"] == "MANAGER"
    created = manager_client.post(
        "/api/actions",
        headers={"X-CSRF-Token": manager["csrf_token"]},
        json={
            "account_id": "boeing",
            "title": f"Hosted approval {uuid4()}",
            "priority": "MEDIUM",
            "approval_required": True,
        },
    )
    assert created.status_code == 200

    seller_client = TestClient(manager_client.app, base_url="https://backend.test")
    seller = _sign_in(seller_client, "hosted-seller-access")
    assert seller["principal"]["role"] == "SALESPERSON"
    # A manager cannot approve their own request. Assign to the seller and
    # record an explicit owner request before exercising the manager decision.
    assert manager_client.post(f"/api/actions/{created.json()['id']}/approval",
        headers={"X-CSRF-Token": manager["csrf_token"]}, json={"decision": "APPROVED"}).status_code == 403
    assigned = manager_client.patch(f"/api/actions/{created.json()['id']}",
        headers={"X-CSRF-Token": manager["csrf_token"]}, json={"owner_id": seller["principal"]["user_id"], "expected_version": created.json()['version']})
    assert assigned.status_code == 200
    requested = seller_client.post(f"/api/actions/{created.json()['id']}/approval/request",
        headers={"X-CSRF-Token": seller["csrf_token"]}, json={"expected_version": assigned.json()['version']})
    assert requested.status_code == 200
    assert (
        seller_client.post(
            f"/api/actions/{created.json()['id']}/approval",
            headers={"X-CSRF-Token": seller["csrf_token"]},
            json={"decision": "APPROVED"},
        ).status_code
        == 403
    )
    assert (
        manager_client.post(
            f"/api/actions/{created.json()['id']}/approval",
            headers={"X-CSRF-Token": manager["csrf_token"]},
            json={"decision": "APPROVED"},
        ).status_code
        == 200
    )


def test_csrf_signout_and_invalid_session_fail_closed(monkeypatch) -> None:
    client = _production_app(monkeypatch)
    session = _sign_in(client, "hosted-seller-access")
    assert client.patch("/api/settings/preferences", json={}).status_code == 403
    assert (
        client.patch(
            "/api/settings/preferences",
            headers={"X-CSRF-Token": session["csrf_token"]},
            json={"compact_density": True},
        ).status_code
        == 200
    )
    assert client.post("/api/session/sign-out").status_code == 403
    assert (
        client.post(
            "/api/session/sign-out",
            headers={"X-CSRF-Token": session["csrf_token"]},
        ).status_code
        == 200
    )
    assert client.get("/api/session").status_code == 401


def test_session_expiration_is_enforced() -> None:
    settings = Settings(
        _env_file=None,
        session_ttl_seconds=60,
        action_salesperson_token="seller-secret",
        action_manager_token="manager-secret",
    )
    store = SessionStore(settings)
    clock = datetime(2026, 8, 28, tzinfo=UTC)
    session = store.exchange("seller-secret", now=clock)
    assert session is not None
    assert store.get(session.id, now=clock + timedelta(seconds=59)) is not None
    assert store.get(session.id, now=clock + timedelta(seconds=61)) is None


def test_sample_demo_bypass_issues_only_a_normal_salesperson_session(monkeypatch) -> None:
    client = _production_app(monkeypatch, hosted_demo_access_bypass=True)
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["principal"] == {
        "user_id": "shared-access",
        "display_name": "POC Salesperson",
        "role": "SALESPERSON",
        "tenant_id": None,
    }
    assert "httponly" in session.headers["set-cookie"].casefold()
    assert client.get("/api/actions").status_code == 200

    created = client.post(
        "/api/actions",
        headers={"X-CSRF-Token": session.json()["csrf_token"]},
        json={
            "account_id": "boeing",
            "title": f"SAMPLE demo approval {uuid4()}",
            "priority": "MEDIUM",
            "approval_required": True,
        },
    )
    assert created.status_code == 200
    assert (
        client.post(
            f"/api/actions/{created.json()['id']}/approval",
            headers={"X-CSRF-Token": session.json()["csrf_token"]},
            json={"decision": "APPROVED"},
        ).status_code
        == 403
    )
    assert _sign_in(client, "hosted-manager-access")["principal"]["role"] == "MANAGER"


def test_demo_bypass_fails_closed_outside_sample_data(monkeypatch) -> None:
    client = _production_app(
        monkeypatch,
        hosted_demo_access_bypass=True,
        data_mode="CONNECTED",
    )
    assert client.get("/api/session").status_code == 401


def test_credentialed_cors_allows_only_canonical_origin(monkeypatch) -> None:
    client = _production_app(monkeypatch)
    allowed = client.options(
        "/api/session",
        headers={
            "Origin": "https://btx-omni-prospect.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://btx-omni-prospect.vercel.app"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    rejected = client.options(
        "/api/session",
        headers={
            "Origin": "https://unapproved-preview.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_release_diagnostics_are_safe_and_exclude_server_credentials(monkeypatch) -> None:
    client = _production_app(monkeypatch)
    session = _sign_in(client, "hosted-manager-access")
    response = client.get("/api/settings")
    assert response.status_code == 200
    diagnostics = response.json()["release_diagnostics"]
    assert diagnostics["api"]["state"] == "AVAILABLE"
    assert diagnostics["session"] == {
        "state": "CONFIGURED",
        "mode": "HOSTED_POC_SESSION",
    }
    serialized = response.text.casefold()
    assert "hosted-seller-access" not in serialized
    assert "hosted-manager-access" not in serialized
    assert session["csrf_token"].casefold() not in serialized
    assert "api_key" not in serialized
    assert "operator_token" not in serialized


def test_public_build_identity_is_same_runtime_but_never_exposes_private_readiness(monkeypatch):
    client = _production_app(monkeypatch, release_sha='a' * 40, release_tree='b' * 40, release_worktree='clean')
    public = client.get('/api/build')
    assert public.status_code == 200 and public.json()['commit_sha'] == 'a' * 40
    assert public.json()['repository'] == 'kas1172-dotcom/btx-omni-prospect'
    assert 'database' not in public.text and 'hosted-seller-access' not in public.text
    assert client.get('/api/settings').status_code == 401
    _sign_in(client, 'hosted-manager-access')
    assert client.get('/api/settings').json()['release_diagnostics']['build'] == public.json()
