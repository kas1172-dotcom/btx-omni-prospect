import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.app import create_app


@pytest.mark.asyncio
async def test_canonical_poc_api_end_to_end_paths() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        southwest = await client.get("/api/map", params={"industry": "Semiconductor"})
        medical = await client.get("/api/map", params={"industry": "Medical Device"})
        accounts = await client.get("/api/accounts")
        defense = await client.get("/api/accounts/acct-02-001")
        no_quote = await client.get("/api/accounts/acct-06-002")
        semiconductor = await client.get("/api/intelligence")
        dormant_omni = await client.post("/api/omni", json={"account_id": "acct-01-003", "question": "Why is it dormant?"})
        stale_omni = await client.post("/api/omni", json={"account_id": "acct-01-004", "question": "Explain quote."})
        cross_bu = await client.post("/api/omni", json={"account_id": "acct-01-005", "question": "Coordinate?"})
        external = await client.post("/api/omni", json={"account_id": "acct-01-006", "question": "What do we know?"})
        conflict = await client.post("/api/omni", json={"account_id": "acct-01-008", "question": "What is missing?"})
    assert southwest.status_code == medical.status_code == accounts.status_code == defense.status_code == no_quote.status_code == 200
    assert len(southwest.json()["records"]) == 100 and len(medical.json()["records"]) == 100
    assert all(item["location"]["country"] == "US" and item["public_research_state"] == "ELIGIBLE" and item["public_identity_state"] == "UNVERIFIED" for item in accounts.json()["accounts"])
    assert all("external_rank" in item and "attractiveness" in item and "commercial_context_state" in item for item in accounts.json()["accounts"])
    assert "intelligence_signals" in southwest.json()
    assert defense.json()["matching"][0]["method"] == "EXACT_PART"
    assert len(defense.json()["paperless_accounts"]) == 1 and len(defense.json()["paperless_quotes"]) == 2
    assert defense.json()["public_identity"] is None and defense.json()["public_identity_state"] == "UNVERIFIED"
    assert len(no_quote.json()["paperless_accounts"]) == 1 and not no_quote.json()["paperless_quotes"]
    assert any(item["kind"] == "EXPANSION" for item in semiconductor.json()["signals"])
    assert "CUSTOMER_INACTIVITY" in dormant_omni.json()["content"]
    assert "STALE_QUOTE" in stale_omni.json()["content"]
    assert "CROSS_BU_COORDINATION" in cross_bu.json()["content"]
    assert external.json()["missingness"] and conflict.json()["missingness"]


@pytest.mark.asyncio
async def test_actions_are_idempotent_confirmed_and_audited() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        body = {"account_id": "acct-01-003", "summary": "Review dormant account", "evidence_ids": ["ev-dormant"], "idempotency_key": "api-dormant-1", "actor_id": "seller"}
        first = await client.post("/api/actions", json=body)
        replay = await client.post("/api/actions", json=body)
        item_id = first.json()["id"]
        transition = await client.post(f"/api/actions/{item_id}/ASSIGNED", json={"actor_id": "manager", "owner_id": "owner-1"})
        denied = await client.post(f"/api/actions/{item_id}/crm-execute")
        executed = await client.post(f"/api/actions/{item_id}/crm-execute", params={"confirmed": "true"})
        audit = await client.get(f"/api/actions/{item_id}/audit")
    assert first.status_code == replay.status_code == transition.status_code == executed.status_code == 200
    assert first.json()["id"] == replay.json()["id"]
    assert denied.status_code == 409 and executed.json()["executed"]
    assert len(audit.json()["events"]) == 2


@pytest.mark.asyncio
async def test_today_health_openapi_and_connected_mode_boundary(monkeypatch) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        today = await client.get("/api/today")
        health = await client.get("/api/health")
        schema = await client.get("/openapi.json")
    assert today.status_code == health.status_code == schema.status_code == 200
    assert "/api/omni" in schema.json()["paths"] and "recommended_actions" in today.json()
