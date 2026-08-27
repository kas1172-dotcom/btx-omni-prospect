import pytest
from httpx import ASGITransport, AsyncClient

from btx_omni.api.map import _account_segment
from btx_omni.app import create_app
from btx_omni.core.config import get_settings


@pytest.mark.asyncio
async def test_canonical_poc_api_end_to_end_paths() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        southwest = await client.get("/api/map", params={"industry": "Semiconductor"})
        medical = await client.get("/api/map", params={"industry": "Medical"})
        accounts = await client.get("/api/accounts")
        defense = await client.get("/api/accounts/lockheed-martin")
        no_quote = await client.get("/api/accounts/symbotic")
        semiconductor = await client.get("/api/intelligence")
        dormant_omni = await client.post(
            "/api/omni",
            json={"account_id": "applied-materials", "question": "Why is it dormant?"},
        )
        stale_omni = await client.post(
            "/api/omni",
            json={"account_id": "lockheed-martin", "question": "Explain quote."},
        )
        cross_bu = await client.post(
            "/api/omni", json={"account_id": "boeing", "question": "Coordinate?"}
        )
        external = await client.post(
            "/api/omni",
            json={"account_id": "rocket-lab-usa", "question": "What do we know?"},
        )
        conflict = await client.post(
            "/api/omni", json={"account_id": "symbotic", "question": "What is missing?"}
        )
    assert (
        southwest.status_code
        == medical.status_code
        == accounts.status_code
        == defense.status_code
        == no_quote.status_code
        == 200
    )
    assert southwest.json()["records"] and medical.json()["records"]
    assert southwest.json()["accounts"] == southwest.json()["records"]
    assert all(
        item["entity_type"] == "ACCOUNT" and item["coordinates"]
        for item in southwest.json()["accounts"]
    )
    assert all(
        item["entity_type"] == "FACILITY"
        and item["facility_id"]
        and item["coordinates"]
        for item in southwest.json()["facilities"]
    )
    assert len(southwest.json()["btx_facilities"]) == 5
    assert all(
        item["entity_type"] == "BTX_FACILITY" and item["coordinates"]
        for item in southwest.json()["btx_facilities"]
    )
    assert all(
        item["verification_state"] == "VERIFIED_PUBLIC_FACILITY"
        and item["provenance"]["source_url"]
        for item in southwest.json()["btx_facilities"]
    )
    assert all(
        item["nearest_btx_facility"] is not None
        and item["nearest_btx_facility"]["id"] != "btx-southwest"
        for item in southwest.json()["records"]
    )
    assert all(
        item["location"] is None or item["location"]["country"]
        for item in accounts.json()["accounts"]
    )
    assert accounts.json()["accounts"] and all(
        item["public_identity_state"] != "UNVERIFIED"
        for item in accounts.json()["accounts"]
    )
    assert all(
        "attractiveness" in item and "commercial_context_state" in item
        for item in accounts.json()["accounts"]
    )
    assert "intelligence_signals" in southwest.json()
    assert all(
        item["coordinates"] is None or item["facility_id"]
        for item in southwest.json()["intelligence"]
    )
    assert defense.json()["matching"][0]["method"] == "EXACT_PART"
    assert (
        len(defense.json()["paperless_accounts"]) == 1
        and len(defense.json()["paperless_quotes"]) == 8
    )
    assert (
        defense.json()["public_identity"] is not None
        and defense.json()["public_identity_state"] != "UNVERIFIED"
    )
    assert (
        not no_quote.json()["paperless_accounts"]
        and not no_quote.json()["paperless_quotes"]
    )
    assert any(item["kind"] == "EXPANSION" for item in semiconductor.json()["signals"])
    intel_signal = next(
        item
        for item in semiconductor.json()["signals"]
        if item["account_id"] == "intel"
    )
    assert intel_signal["source_validation_state"] == "AUTOMATION_BLOCKED"
    assert (
        intel_signal["source_url"]
        == "https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-intel"
    )
    assert intel_signal["observed_at"].startswith("2024-11-26")
    assert defense.json()["public_relationship"]["state"] == "NO_RELATIONSHIP_EVIDENCE"
    assert all(
        "linkedin.com" not in (contact.get("source_url") or "").casefold()
        for contact in defense.json()["public_contacts"]
    )
    assert dormant_omni.json()["recommended_action"]
    assert stale_omni.json()["recommended_action"]
    assert "CROSS_BU_COORDINATION" in cross_bu.json()["content"]
    assert external.json()["citations"] and conflict.json()["citations"]


@pytest.mark.asyncio
async def test_map_projects_existing_sample_commercial_segments_without_public_inference() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/map")
    records = {item["account_id"]: item for item in response.json()["accounts"]}
    assert response.status_code == 200
    assert records["lockheed-martin"]["account_segment"] == "CURRENT_CLIENT"
    assert records["applied-materials"]["account_segment"] == "DORMANT_CUSTOMER"
    assert records["anduril-industries"]["account_segment"] == "PROSPECT"
    assert (
        _account_segment(
            account_id="intel",
            active_client_account_ids=set(),
            dormant_customer_account_ids=set(),
            prospect_account_ids=set(),
        )
        == "UNKNOWN"
    )
    assert (
        _account_segment(
            account_id="public-only",
            active_client_account_ids=set(),
            dormant_customer_account_ids=set(),
            prospect_account_ids=set(),
        )
        == "UNKNOWN"
    )
    assert {item["account_segment"] for item in records.values()} <= {
        "CURRENT_CLIENT",
        "DORMANT_CUSTOMER",
        "PROSPECT",
        "UNKNOWN",
    }


@pytest.mark.asyncio
async def test_actions_are_idempotent_confirmed_and_audited() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        seller = {"X-BTX-Principal-Token": "development-salesperson"}
        body = {
            "account_id": "applied-materials",
            "title": "Review dormant Customer",
            "evidence_ids": ["ev-dormant"],
            "idempotency_key": "api-dormant-v2",
        }
        high = {
            "account_id": "boeing",
            "title": "High-priority review",
            "evidence_ids": ["FAA_BOEING"],
            "idempotency_key": "api-high-v2",
            "priority": "HIGH",
        }
        first = await client.post("/api/actions", json=body, headers=seller)
        replay = await client.post("/api/actions", json=body, headers=seller)
        item_id = first.json()["id"]
        high_item = await client.post("/api/actions", json=high, headers=seller)
        transition = await client.post(
            f"/api/actions/{item_id}/status",
            json={"status": "IN_PROGRESS"},
            headers=seller,
        )
        denied = await client.post(
            f"/api/actions/{item_id}/crm-execute", headers=seller
        )
        audit = await client.get(f"/api/actions/{item_id}/history", headers=seller)
        listed = await client.get("/api/actions", headers=seller)
    assert (
        first.status_code
        == replay.status_code
        == transition.status_code
        == high_item.status_code
        == 200
    )
    assert first.json()["id"] == replay.json()["id"]
    assert denied.status_code == 409
    assert len(audit.json()["events"]) == 2
    assert listed.json()["items"][0]["id"] == high_item.json()["id"]
    assert listed.json()["items"][0]["priority"] == "HIGH"
    assert listed.json()["persistence"] == "DURABLE_DATABASE"


@pytest.mark.asyncio
async def test_omni_accepts_an_unscoped_question_with_truthful_fallback() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/omni", json={"question": "Which researched targets should I review?"}
        )
    assert response.status_code == 200
    payload = response.json()
    assert "curated public-company universe" in payload["content"]
    assert "not model-generated advice" in payload["content"]
    assert payload["citation_links"] and payload["recommended_action"]


@pytest.mark.asyncio
async def test_omni_typed_context_is_bounded_and_backwards_compatible() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        typed = await client.post(
            "/api/omni",
            json={
                "question": "Why is this account attractive?",
                "context": {
                    "surface": "account_detail",
                    "selected_account_id": "boeing",
                    "selected_event_id": "event-123",
                    "session_account_id": "boeing",
                    "active_filters": {"market": "Defense"},
                    "visible_record_ids": ["boeing"],
                    "prior_turns": "user: Boeing",
                },
            },
        )
        intelligence_context = await client.post(
            "/api/omni",
            json={
                "question": "What matters most here?",
                "context": {
                    "surface": "INTELLIGENCE",
                    "selected_event_id": "event-123",
                    "active_filters": {"market": "Defense"},
                    "visible_record_ids": ["event-123", "event-456"],
                },
            },
        )
        map_context = await client.post(
            "/api/omni",
            json={
                "question": "What matters here?",
                "context": {
                    "surface": "MAP",
                    "selected_account_id": "boeing",
                    "selected_facility_id": "facility-123",
                },
            },
        )
        action_context = await client.post(
            "/api/omni",
            json={
                "question": "Why was this created?",
                "context": {
                    "surface": "ACTIONS",
                    "selected_action_id": "work-item-123",
                },
            },
        )
        monitor_context = await client.post(
            "/api/omni",
            json={
                "question": "What am I looking at?",
                "context": {"surface": "MONITOR"},
            },
        )
        monitor_context_exact = await client.post(
            "/api/omni",
            json={
                "question": "What Monitor context is active?",
                "context": {"surface": "MONITOR", "prior_turns": ""},
            },
        )
        monitor_global = await client.post(
            "/api/omni",
            json={
                "question": "Which accounts have the highest scores?",
                "context": {"surface": "MONITOR"},
            },
        )
        legacy = await client.post(
            "/api/omni",
            json={
                "question": "Why is this account attractive?",
                "context": {
                    "surface": "accounts",
                    "session_account_id": "boeing",
                    "prior_turns": "user: Boeing",
                },
            },
        )
        invalid_surface = await client.post(
            "/api/omni", json={"question": "x", "context": {"surface": "settings"}}
        )
        oversized = await client.post(
            "/api/omni",
            json={
                "question": "x",
                "context": {"visible_record_ids": [str(value) for value in range(51)]},
            },
        )
    assert (
        typed.status_code
        == legacy.status_code
        == intelligence_context.status_code
        == map_context.status_code
        == action_context.status_code
        == monitor_context.status_code
        == monitor_context_exact.status_code
        == monitor_global.status_code
        == 200
    )
    assert typed.json()["context_used"] == {
        "account_id": "boeing",
        "surface": "ACCOUNT_DETAIL",
    }
    assert legacy.json()["context_used"] == {
        "account_id": "boeing",
        "surface": "ACCOUNTS",
    }
    assert monitor_context.json()["context_used"] == {"surface": "MONITOR"}
    assert monitor_context_exact.json()["context_used"] == {"surface": "MONITOR"}
    assert "Monitor exposes status and provenance" in monitor_context.json()["content"]
    assert monitor_global.json()["context_used"] == {}
    assert invalid_surface.status_code == oversized.status_code == 422


@pytest.mark.asyncio
async def test_omni_resolves_selected_intelligence_events_through_the_canonical_projection() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        signals = await client.get("/api/intelligence")
        selected = next(
            item for item in signals.json()["signals"] if item["account_id"] == "boeing"
        )
        response = await client.post(
            "/api/omni",
            json={
                "question": "What evidence supports this?",
                "context": {
                    "surface": "INTELLIGENCE",
                    "selected_event_id": selected["id"],
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert selected["title"] in payload["content"]
    assert payload["context_used"] == {
        "event_id": selected["id"],
        "surface": "INTELLIGENCE",
        "account_id": "boeing",
    }
    assert payload["citation_links"]


@pytest.mark.asyncio
async def test_omni_resolves_selected_facilities_through_the_canonical_map_records() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        map_response = await client.get("/api/map")
        selected = next(
            item
            for item in map_response.json()["facilities"]
            if item["account_id"] == "boeing"
        )
        response = await client.post(
            "/api/omni",
            json={
                "question": "Tell me about this facility.",
                "context": {
                    "surface": "MAP",
                    "selected_facility_id": selected["facility_id"],
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert selected["name"] in payload["content"]
    assert payload["context_used"] == {
        "facility_id": selected["facility_id"],
        "surface": "MAP",
    }
    assert payload["citation_links"]


@pytest.mark.asyncio
async def test_omni_resolves_selected_actions_through_the_canonical_work_service() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/actions",
            headers={"X-BTX-Principal-Token": "development-salesperson"},
            json={
                "account_id": "boeing",
                "title": "Review Boeing public evidence",
                "evidence_ids": ["FAA_BOEING"],
                "idempotency_key": "omni-selected-action-v2",
                "priority": "HIGH",
            },
        )
        response = await client.post(
            "/api/omni",
            json={
                "question": "Why was this created?",
                "context": {
                    "surface": "ACTIONS",
                    "selected_action_id": created.json()["id"],
                },
            },
        )
    payload = response.json()
    assert created.status_code == response.status_code == 200
    assert "Review Boeing public evidence" in payload["content"]
    assert payload["context_used"] == {
        "action_id": created.json()["id"],
        "surface": "ACTIONS",
        "account_id": "boeing",
    }


@pytest.mark.asyncio
async def test_omni_resolves_relationship_questions_through_the_canonical_service() -> (
    None
):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/omni",
            json={
                "question": "How are Boeing and Spirit AeroSystems connected?",
                "context": {
                    "surface": "ACCOUNT_DETAIL",
                    "selected_account_id": "lockheed-martin",
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert "Boeing --PARENT_CHILD_REVERSE--> Spirit AeroSystems" in payload["content"]
    assert payload["context_used"]["account_id"] == "boeing"
    assert payload["context_used"]["related_account_id"] == "spirit-aerosystems"


@pytest.mark.asyncio
async def test_omni_summarizes_only_the_current_canonical_screen_view() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/omni",
            json={
                "question": "What matters most on this page?",
                "context": {
                    "surface": "ACCOUNTS",
                    "active_filters": {"market": "Defense"},
                    "visible_record_ids": ["boeing", "lockheed-martin"],
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert "Current Accounts view" in payload["content"]
    assert "Boeing" in payload["content"] and "Lockheed Martin" in payload["content"]
    assert "Northrop Grumman" not in payload["content"]
    assert payload["context_used"] == {
        "surface": "ACCOUNTS",
        "filters": {"market": "Defense"},
    }


@pytest.mark.asyncio
async def test_omni_cross_account_score_ranking_uses_typed_market_filter() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/omni",
            json={
                "question": "Which accounts have the highest scores?",
                "context": {
                    "surface": "ACCOUNTS",
                    "active_filters": {"market": "Defense"},
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert (
        "Ranked by the existing canonical Account Attractiveness score"
        in payload["content"]
    )
    assert payload["context_used"] == {"filters": {"market": "Defense"}}


@pytest.mark.asyncio
async def test_omni_accepts_bounded_typed_conversation_referents() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        signals = await client.get("/api/intelligence")
        event = next(
            item for item in signals.json()["signals"] if item["account_id"] == "boeing"
        )
        response = await client.post(
            "/api/omni",
            json={
                "question": "Which account is it tied to?",
                "context": {
                    "surface": "ACCOUNTS",
                    "conversation_referent": {
                        "event_id": event["id"],
                        "account_id": "boeing",
                        "route": "EVENT",
                    },
                },
            },
        )
    payload = response.json()
    assert response.status_code == 200
    assert payload["context_used"]["event_id"] == event["id"]
    assert payload["context_used"]["context_source"] == "conversation"
    assert payload["conversation_referent"]["event_id"] == event["id"]


@pytest.mark.asyncio
async def test_today_health_openapi_and_connected_mode_boundary(monkeypatch) -> None:
    monkeypatch.setenv("BTX_MONITOR_MODE", "disabled")
    monkeypatch.setenv("BTX_MONITOR_DURABLE_STATE_ENABLED", "false")
    get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        today = await client.get("/api/today")
        health = await client.get("/api/health")
        schema = await client.get("/openapi.json")
        monitor = await client.get("/api/monitor/health")
    assert today.status_code == health.status_code == schema.status_code == 200
    assert (
        "/api/omni" in schema.json()["paths"] and "recommended_actions" in today.json()
    )
    assert not monitor.json()["collection_enabled"]
    assert "Live ingestion is inactive" in monitor.json()["seller_message"]
    assert len(monitor.json()["curated_preview"]) == 12
    assert all(
        item["data_mode"] == "CURATED_PUBLIC"
        for item in monitor.json()["curated_preview"]
    )
    assert all(
        item["source_url"].startswith("https://")
        for item in monitor.json()["curated_preview"]
    )
    get_settings.cache_clear()
