from fastapi.testclient import TestClient

import btx_omni.app as app_module
from btx_omni.core.config import Settings


def test_tenant_comes_only_from_server_setting_and_spoofing_is_ignored(monkeypatch):
    settings = Settings(_env_file=None, environment="development", omni_tenant_id="server-tenant", database_url="sqlite://")
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    client = TestClient(app_module.create_app())
    response = client.get("/api/session?tenant_id=spoofed", headers={"X-OMNI-Tenant-ID":"spoofed"})
    # Development session status still requires a cookie; inspect an authenticated route's principal instead.
    assert response.status_code == 401
    from btx_omni.api.session import principal
    request = type("Request", (), {"method":"GET", "cookies":{}})()
    value = principal(request, runtime=app_module.runtime, development_token=None, csrf_token=None)
    assert value.tenant_id == "server-tenant"
