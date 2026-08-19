import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.app import create_app
from btx_omni.core.config import get_settings


@pytest.mark.asyncio
async def test_canonical_poc_api_end_to_end_paths() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        southwest = await client.get("/api/map", params={"industry": "Semiconductor"})
        medical = await client.get("/api/map", params={"industry": "Medical"})
        accounts = await client.get("/api/accounts")
        defense = await client.get("/api/accounts/lockheed-martin")
        no_quote = await client.get("/api/accounts/symbotic")
        semiconductor = await client.get("/api/intelligence")
        dormant_omni = await client.post("/api/omni", json={"account_id": "applied-materials", "question": "Why is it dormant?"})
        stale_omni = await client.post("/api/omni", json={"account_id": "lockheed-martin", "question": "Explain quote."})
        cross_bu = await client.post("/api/omni", json={"account_id": "boeing", "question": "Coordinate?"})
        external = await client.post("/api/omni", json={"account_id": "rocket-lab-usa", "question": "What do we know?"})
        conflict = await client.post("/api/omni", json={"account_id": "symbotic", "question": "What is missing?"})
    assert southwest.status_code == medical.status_code == accounts.status_code == defense.status_code == no_quote.status_code == 200
    assert southwest.json()["records"] and medical.json()["records"]
    assert southwest.json()["accounts"] == southwest.json()["records"]
    assert all(item["entity_type"] == "ACCOUNT" and item["coordinates"] for item in southwest.json()["accounts"])
    assert all(item["entity_type"] == "FACILITY" and item["facility_id"] and item["coordinates"] for item in southwest.json()["facilities"])
    assert len(southwest.json()["btx_facilities"]) == 5
    assert all(item["entity_type"] == "BTX_FACILITY" and item["coordinates"] for item in southwest.json()["btx_facilities"])
    assert all(item["verification_state"] == "VERIFIED_PUBLIC_FACILITY" and item["provenance"]["source_url"] for item in southwest.json()["btx_facilities"])
    assert all(item["nearest_btx_facility"] is not None and item["nearest_btx_facility"]["id"] != "btx-southwest" for item in southwest.json()["records"])
    assert all(item["location"] is None or item["location"]["country"] for item in accounts.json()["accounts"])
    assert accounts.json()["accounts"] and all(item["public_identity_state"] != "UNVERIFIED" for item in accounts.json()["accounts"])
    assert all("attractiveness" in item and "commercial_context_state" in item for item in accounts.json()["accounts"])
    assert "intelligence_signals" in southwest.json()
    assert all(item["coordinates"] is None or item["facility_id"] for item in southwest.json()["intelligence"])
    assert defense.json()["matching"][0]["method"] == "EXACT_PART"
    assert len(defense.json()["paperless_accounts"]) == 1 and len(defense.json()["paperless_quotes"]) == 8
    assert defense.json()["public_identity"] is not None and defense.json()["public_identity_state"] != "UNVERIFIED"
    assert not no_quote.json()["paperless_accounts"] and not no_quote.json()["paperless_quotes"]
    assert any(item["kind"] == "EXPANSION" for item in semiconductor.json()["signals"])
    intel_signal = next(item for item in semiconductor.json()["signals"] if item["account_id"] == "intel")
    assert intel_signal["source_validation_state"] == "AUTOMATION_BLOCKED"
    assert intel_signal["source_url"] == "https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-intel"
    assert intel_signal["observed_at"].startswith("2024-11-26")
    assert defense.json()["public_relationship"]["state"] == "NO_RELATIONSHIP_EVIDENCE"
    assert all("linkedin.com" not in (contact.get("source_url") or "").casefold() for contact in defense.json()["public_contacts"])
    assert dormant_omni.json()["recommended_action"]
    assert stale_omni.json()["recommended_action"]
    assert "CROSS_BU_COORDINATION" in cross_bu.json()["content"]
    assert external.json()["citations"] and conflict.json()["citations"]


@pytest.mark.asyncio
async def test_actions_are_idempotent_confirmed_and_audited() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        body = {"account_id": "acct-01-003", "summary": "Review dormant account", "evidence_ids": ["ev-dormant"], "idempotency_key": "api-dormant-1", "actor_id": "seller"}
        high = {"account_id": "boeing", "summary": "High-priority review", "evidence_ids": ["FAA_BOEING"], "idempotency_key": "api-high-1", "actor_id": "seller", "priority": "HIGH"}
        first = await client.post("/api/actions", json=body)
        replay = await client.post("/api/actions", json=body)
        item_id = first.json()["id"]
        high_item = await client.post("/api/actions", json=high)
        transition = await client.post(f"/api/actions/{item_id}/ASSIGNED", json={"actor_id": "manager", "owner_id": "owner-1"})
        denied = await client.post(f"/api/actions/{item_id}/crm-execute")
        executed = await client.post(f"/api/actions/{item_id}/crm-execute", params={"confirmed": "true"})
        audit = await client.get(f"/api/actions/{item_id}/audit")
        listed = await client.get("/api/actions")
    assert first.status_code == replay.status_code == transition.status_code == executed.status_code == high_item.status_code == 200
    assert first.json()["id"] == replay.json()["id"]
    assert denied.status_code == 409 and executed.json()["executed"]
    assert len(audit.json()["events"]) == 2
    assert listed.json()["items"][0]["id"] == high_item.json()["id"]
    assert listed.json()["items"][0]["priority"] == "HIGH"
    assert listed.json()["persistence"] == "SESSION_MEMORY_ONLY"


@pytest.mark.asyncio
async def test_omni_accepts_an_unscoped_question_with_truthful_fallback() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        response = await client.post("/api/omni", json={"question": "Which researched targets should I review?"})
    assert response.status_code == 200
    payload = response.json()
    assert "curated public-company universe" in payload["content"]
    assert "not model-generated advice" in payload["content"]
    assert payload["citation_links"] and payload["recommended_action"]


@pytest.mark.asyncio
async def test_omni_typed_context_is_bounded_and_backwards_compatible() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        typed = await client.post("/api/omni", json={"question": "Why is this account attractive?", "context": {"surface": "account_detail", "selected_account_id": "boeing", "selected_event_id": "event-123", "session_account_id": "boeing", "active_filters": {"market": "Defense"}, "visible_record_ids": ["boeing"], "prior_turns": "user: Boeing"}})
        legacy = await client.post("/api/omni", json={"question": "Why is this account attractive?", "context": {"surface": "accounts", "session_account_id": "boeing", "prior_turns": "user: Boeing"}})
        invalid_surface = await client.post("/api/omni", json={"question": "x", "context": {"surface": "settings"}})
        oversized = await client.post("/api/omni", json={"question": "x", "context": {"visible_record_ids": [str(value) for value in range(51)]}})
    assert typed.status_code == legacy.status_code == 200
    assert typed.json()["context_used"] == {"account_id": "boeing", "surface": "ACCOUNT_DETAIL"}
    assert legacy.json()["context_used"] == {"account_id": "boeing", "surface": "ACCOUNTS"}
    assert invalid_surface.status_code == oversized.status_code == 422


@pytest.mark.asyncio
async def test_today_health_openapi_and_connected_mode_boundary(monkeypatch) -> None:
    monkeypatch.setenv("BTX_MONITOR_MODE", "disabled")
    monkeypatch.setenv("BTX_MONITOR_DURABLE_STATE_ENABLED", "false")
    get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        today = await client.get("/api/today")
        health = await client.get("/api/health")
        schema = await client.get("/openapi.json")
        monitor = await client.get("/api/monitor/health")
    assert today.status_code == health.status_code == schema.status_code == 200
    assert "/api/omni" in schema.json()["paths"] and "recommended_actions" in today.json()
    assert not monitor.json()["collection_enabled"]
    assert "Live ingestion is inactive" in monitor.json()["seller_message"]
    assert len(monitor.json()["curated_preview"]) == 12
    assert all(item["data_mode"] == "CURATED_PUBLIC" for item in monitor.json()["curated_preview"])
    assert all(item["source_url"].startswith("https://") for item in monitor.json()["curated_preview"])
    get_settings.cache_clear()
