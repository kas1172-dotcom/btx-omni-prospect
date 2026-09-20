from dataclasses import replace

from fastapi.testclient import TestClient

from btx_omni.app import create_app
from btx_omni.modules.accounts.customer_360 import customer_360_projection
from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.providers.sample.environment import build_sample_environment


def test_customer_360_is_canonical_and_projects_bounded_joined_context() -> None:
    client = TestClient(create_app())
    response = client.get("/api/accounts/lockheed-martin")
    assert response.status_code == 200
    body = response.json()["customer_360"]
    assert body["commercial"]["source_state"] == {"data_mode": "SAMPLE", "source_state": "AVAILABLE"}
    assert body["quotes"]["records"]
    assert body["orders"]["records"]
    assert body["programs"]
    assert body["components"]
    assert body["capabilities"]
    assert len(body["quotes"]["records"]) <= 10


def test_prospect_360_does_not_turn_absence_into_commercial_zero() -> None:
    client = TestClient(create_app())
    body = client.get("/api/accounts/intel").json()["customer_360"]
    assert body["commercial"]["records"] == []
    assert body["commercial"]["missing"] == "No linked commercial history"
    assert body["quotes"]["records"] == []
    assert body["orders"]["records"] == []
    assert body["crm"]["contacts"] == []
    assert body["programs"] == []
    assert body["components"] == []


def test_customer_360_has_no_name_based_fallback() -> None:
    client = TestClient(create_app())
    assert client.get("/api/accounts/HUXWRX").status_code == 404


def test_projection_preserves_provider_unavailability_without_hiding_governed_relevance() -> None:
    sample = build_sample_environment()
    commercial = CommercialReadService(
        sample,
        source_states={"commercial": ("CONNECTED", "UNAVAILABLE")},
    ).account_snapshot("lockheed-martin")
    commercial = replace(commercial, commercial_context=())
    projection = customer_360_projection(
        account_id="lockheed-martin", sample=sample, commercial=commercial, signals=[]
    )
    assert projection["commercial"]["source_state"] == {
        "data_mode": "CONNECTED",
        "source_state": "UNAVAILABLE",
    }
    assert projection["commercial"]["records"] == []
    assert projection["components"]
    assert projection["capabilities"]


def test_projection_is_stably_ordered_and_bounded() -> None:
    sample = build_sample_environment()
    commercial = CommercialReadService(sample).account_snapshot("lockheed-martin")
    projection = customer_360_projection(
        account_id="lockheed-martin", sample=sample, commercial=commercial, signals=[]
    )
    assert len(projection["quotes"]["records"]) <= 10
    assert len(projection["orders"]["records"]) <= 10
    assert [item["name"] for item in projection["programs"]] == sorted(
        item["name"] for item in projection["programs"]
    )
