from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.account_planning import router
from btx_omni.api.accounts import get_runtime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence.account_planning import (
    AccountPlanningConflict,
    AccountPlanningRepository,
)
from btx_omni.persistence.models import (
    account_partnership_audit,
    account_partnership_designations,
    seller_shortlist_items,
)
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 9, 8, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'planning.db'}", connect_args={"check_same_thread": False})
    for table in (account_partnership_designations, account_partnership_audit, seller_shortlist_items):
        table.create(engine)
    return AccountPlanningRepository(engine)


def test_designations_are_audited_versioned_and_replay_safe(repository):
    first = repository.designate(account_id="boeing", designated=True, reason="Joint pursuit review approved for the sample workspace.",
        actor_id="manager-1", expected_version=None, idempotency_key="designation-one", now=NOW)
    assert first["version"] == 1 and first["designated"] is True
    assert repository.designate(account_id="boeing", designated=True, reason="Joint pursuit review approved for the sample workspace.",
        actor_id="manager-1", expected_version=None, idempotency_key="designation-one", now=NOW) == first
    removed = repository.designate(account_id="boeing", designated=False, reason="Review concluded without an active partnership designation.",
        actor_id="manager-1", expected_version=1, idempotency_key="designation-two", now=NOW + timedelta(seconds=1))
    assert removed["version"] == 2
    assert repository.view("seller-1")["strategic_partnerships"] == []
    with repository.engine.connect() as connection:
        assert len(connection.execute(account_partnership_audit.select()).all()) == 2
    with pytest.raises(AccountPlanningConflict, match="reload"):
        repository.designate(account_id="boeing", designated=True, reason="A stale manager decision must not overwrite current state.",
            actor_id="manager-1", expected_version=1, idempotency_key="designation-three", now=NOW)


def test_shortlists_are_private_dated_and_idempotent(repository):
    item = repository.save_shortlist(user_id="seller-1", account_id="kla", kind="GROWTH",
        objective="Validate the cross-business-unit component fit.", target_date="2026-10-01", active=True,
        expected_version=None, idempotency_key="shortlist-one", now=NOW)
    assert item["version"] == 1
    assert repository.view("seller-1")["shortlist"][0]["account_id"] == "kla"
    assert repository.view("seller-2")["shortlist"] == []
    assert repository.save_shortlist(user_id="seller-1", account_id="kla", kind="GROWTH",
        objective="Validate the cross-business-unit component fit.", target_date="2026-10-01", active=True,
        expected_version=None, idempotency_key="shortlist-one", now=NOW) == item


def test_api_authorizes_designation_and_validates_canonical_accounts(repository):
    sample = build_sample_environment()
    runtime = type("Runtime", (), {"account_planning": repository, "environment": lambda self: sample})()
    actor = {"value": Principal("seller-1", "Seller", PrincipalRole.SALESPERSON)}
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_runtime] = lambda: runtime
    app.dependency_overrides[principal] = lambda: actor["value"]
    client = TestClient(app)

    designation = {"designated": True, "reason": "A manager reviewed the partnership classification.", "expected_version": None, "idempotency_key": "api-partner-one"}
    assert client.post("/api/planning/partnerships/boeing", json=designation).status_code == 403
    actor["value"] = Principal("manager-1", "Manager", PrincipalRole.MANAGER)
    assert client.post("/api/planning/partnerships/not-an-account", json=designation).status_code == 404
    response = client.post("/api/planning/partnerships/boeing", json=designation)
    assert response.status_code == 200 and response.json()["updated_by"] == "manager-1"

    actor["value"] = Principal("seller-1", "Seller", PrincipalRole.SALESPERSON)
    shortlist = {"account_id": "kla", "kind": "RESEARCH", "objective": "Confirm buyer access and technical qualification evidence.", "target_date": "2026-10-01", "active": True, "expected_version": None, "idempotency_key": "api-shortlist-one"}
    assert client.post("/api/planning/shortlist", json=shortlist).status_code == 200
    view = client.get("/api/planning").json()
    assert view["shortlist"][0]["account_id"] == "kla"
    assert view["strategic_partnerships"][0]["account_id"] == "boeing"
    assert client.post("/api/planning/shortlist", json={**shortlist, "account_id": "absent", "idempotency_key": "api-shortlist-two"}).status_code == 404
