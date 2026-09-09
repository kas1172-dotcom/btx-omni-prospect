from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.accounts import get_runtime
from btx_omni.api.itineraries import router
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.itineraries import ItineraryConflict, ItineraryRepository
from btx_omni.persistence.models import seller_itineraries
from btx_omni.providers.sample.environment import build_sample_environment


def _payload(name="Boeing headquarters"):
    return {
        "origin_label": "BTX Minneapolis",
        "origin_latitude": "44.9778",
        "origin_longitude": "-93.2650",
        "stops": [{
            "id": "stop-boeing",
            "account_id": "boeing",
            "facility_id": "public-hq-boeing",
            "site_name": name,
            "latitude": "38.8816",
            "longitude": "-77.091",
            "purpose": "Review recovery plan",
            "contact_name": "",
            "meeting_status": "NOT_REQUESTED",
            "visit_brief": "Confirm scope before outreach.",
            "travel_distance_miles": None,
            "travel_duration_minutes": None,
            "route_provider": None,
            "route_retrieved_at": None,
        }],
    }


def test_itinerary_is_principal_scoped_versioned_and_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'itinerary.db'}")
    seller_itineraries.create(engine)
    repository = ItineraryRepository(engine)
    now = datetime(2026, 9, 8, tzinfo=UTC)

    first = repository.save(user_id="seller-1", title="Southwest trip", payload=_payload(),
                            idempotency_key="save-one", expected_version=None, now=now)
    replay = repository.save(user_id="seller-1", title="Southwest trip", payload=_payload(),
                             idempotency_key="save-one", expected_version=None, now=now)
    assert first == replay
    assert first["version"] == 1
    assert repository.get("seller-2") is None

    second = repository.save(user_id="seller-1", title="Southwest trip", payload=_payload("Boeing Arlington"),
                             idempotency_key="save-two", expected_version=1, now=now)
    assert second["version"] == 2
    assert second["stops"][0]["site_name"] == "Boeing Arlington"

    import pytest

    with pytest.raises(ItineraryConflict, match="reload"):
        repository.save(user_id="seller-1", title="Stale", payload=_payload(),
                        idempotency_key="save-three", expected_version=1, now=now)
    with pytest.raises(ItineraryConflict, match="different itinerary content"):
        repository.save(user_id="seller-1", title="Changed", payload=_payload(),
                        idempotency_key="save-two", expected_version=2, now=now)


def test_itinerary_api_validates_scope_coordinates_and_duplicate_stops(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'itinerary-api.db'}", connect_args={"check_same_thread": False})
    seller_itineraries.create(engine)
    sample = build_sample_environment()
    runtime = type("Runtime", (), {"itineraries": ItineraryRepository(engine), "environment": lambda self: sample})()
    current = Principal("seller-1", "Seller One", PrincipalRole.SALESPERSON)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_runtime] = lambda: runtime
    app.dependency_overrides[principal] = lambda: current
    client = TestClient(app)

    body = {"title": "Southwest trip", **_payload(), "idempotency_key": "browser-save-one"}
    response = client.post("/api/itineraries/current", json=body)
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert client.get("/api/itineraries/current").json()["itinerary"]["stops"][0]["account_id"] == "boeing"

    invalid = {**body, "idempotency_key": "browser-save-two", "stops": [body["stops"][0], body["stops"][0]]}
    assert client.post("/api/itineraries/current", json=invalid).status_code == 422
    invalid = {**body, "idempotency_key": "browser-save-three", "stops": [{**body["stops"][0], "latitude": "91"}]}
    assert client.post("/api/itineraries/current", json=invalid).status_code == 422
    invalid = {**body, "idempotency_key": "browser-save-four", "stops": [{**body["stops"][0], "facility_id": "made-up-site"}]}
    assert client.post("/api/itineraries/current", json=invalid).status_code == 422
    invalid = {**body, "idempotency_key": "browser-save-five", "origin_longitude": None}
    assert client.post("/api/itineraries/current", json=invalid).status_code == 422
