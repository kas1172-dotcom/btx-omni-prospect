from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_network_visibility import repository_with_row

from btx_omni.core.config import Settings
from btx_omni.persistence import models
from btx_omni.security.sessions import SessionStore


def settings():
    return Settings(_env_file=None, environment="production", omni_tenant_id="tenant-a",
                    database_url="sqlite://", user_access_code_hashes={
                        user: sha256(code.encode()).hexdigest()
                        for user, code in (("seller-1", "fake-code-one"), ("seller-2", "fake-code-two"))})


def test_distinct_server_users_and_shared_access_visibility():
    config = settings()
    config.action_salesperson_token = "fake-shared-code"
    store = SessionStore(config)
    first = store.exchange("fake-code-one").principal
    second = store.exchange("fake-code-two").principal
    shared = store.exchange("fake-shared-code").principal
    repo = repository_with_row()
    assert first.user_id == "seller-1" and second.user_id == "seller-2"
    assert len(repo.visible_rows(first)) == 1
    assert repo.visible_rows(second) == ()
    assert shared.user_id == "shared-access"
    with repo.engine.begin() as conn:
        conn.execute(update(models.network_import_batches).values(owner_user_id="shared-access"))
    assert repo.visible_rows(shared) == ()
    assert not repo.share_batch("batch", tenant_id="tenant-a", owner_user_id="shared-access")


def test_hosted_defaults_and_ambiguous_codes_fail_closed():
    config = settings()
    store = SessionStore(config)
    assert store.production_configured
    assert store.exchange("development-salesperson") is None
    assert store.exchange("development-manager") is None
    assert store.exchange("unknown") is None
    config.action_salesperson_token = "fake-code-one"
    assert store.exchange("fake-code-one") is None
    with pytest.raises(ValueError):
        Settings(_env_file=None, user_access_code_hashes={"shared-access": "a" * 64})
    with pytest.raises(ValueError):
        Settings(_env_file=None, user_access_code_hashes={"one": "a" * 64, "two": "a" * 64})


def test_header_query_cookie_and_body_cannot_select_identity(monkeypatch):
    import btx_omni.app as module
    monkeypatch.setattr(module, "runtime", module.runtime)
    monkeypatch.setattr(module, "get_settings", settings)
    with TestClient(module.create_app(), base_url="https://backend.test") as client:
        client.cookies.set("user_id", "seller-2")
        client.cookies.set("tenant_id", "spoofed")
        response = client.post("/api/session/sign-in?user_id=seller-2&tenant_id=spoofed",
                               headers={"X-User-Id": "seller-2", "X-Tenant-Id": "spoofed"},
                               json={"access_code": "fake-code-one", "user_id": "seller-2", "tenant_id": "spoofed"})
        assert response.status_code == 200
        assert response.json()["principal"]["user_id"] == "seller-1"
        assert response.json()["principal"]["tenant_id"] == "tenant-a"
        assert client.get("/api/actions/principal?user_id=seller-2", headers={"X-User-Id": "seller-2"}).json()["user_id"] == "seller-1"
    with TestClient(module.create_app(), base_url="https://backend.test") as client:
        assert client.get("/api/actions", headers={"X-BTX-Principal-Token": "development-salesperson"}).status_code == 401
