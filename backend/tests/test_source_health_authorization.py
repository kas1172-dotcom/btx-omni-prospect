import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.app import create_app


@pytest.mark.asyncio
async def test_source_health_requires_manager_and_does_not_leak_operational_metadata() -> None:
    seller = {"X-BTX-Principal-Token": "development-salesperson"}
    manager = {"X-BTX-Principal-Token": "development-manager"}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        denied = await client.get("/api/monitor/health", headers=seller)
        denied_sources = await client.get("/api/monitor/sources", headers=seller)
        allowed = await client.get("/api/monitor/health", headers=manager)

    assert denied.status_code == denied_sources.status_code == 403
    assert denied.json() == {"detail": "This administrator workspace is unavailable."}
    denied_text = denied.text.casefold()
    assert "sam.gov" not in denied_text and "scheduler" not in denied_text and "source_id" not in denied_text
    assert allowed.status_code == 200
    assert "scheduler_state" in allowed.json() and "sources" in allowed.json()


@pytest.mark.asyncio
async def test_settings_exposes_role_capabilities_and_withholds_release_diagnostics_from_seller() -> None:
    seller = {"X-BTX-Principal-Token": "development-salesperson"}
    manager = {"X-BTX-Principal-Token": "development-manager"}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        seller_settings = await client.get("/api/settings", headers=seller)
        manager_settings = await client.get("/api/settings", headers=manager)

    assert seller_settings.status_code == manager_settings.status_code == 200
    seller_payload = seller_settings.json()
    manager_payload = manager_settings.json()
    assert seller_payload["capabilities"]["view_source_health"] is False
    assert seller_payload["capabilities"]["view_integration_diagnostics"] is False
    assert seller_payload["release_diagnostics"] is None
    assert manager_payload["capabilities"]["view_source_health"] is True
    assert manager_payload["capabilities"]["view_integration_diagnostics"] is True
    assert manager_payload["release_diagnostics"]["database"]["required_revision"]
