"""API response contracts for the SAMPLE render-check fixes; no scorer changes."""

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.accounts import PUBLIC_RELATIONSHIP_LABELS, account_360, accounts, get_runtime
from btx_omni.api.commercial import commercial_evidence, opportunity_workspace, router as commercial_router
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.core.config import Settings
from btx_omni.persistence.models import metadata


NAMES = (
    "boeing", "lockheed-martin", "northrop-grumman", "ge-aerospace",
    "anduril-industries", "blue-origin", "rocket-lab-usa", "applied-materials",
    "medtronic", "intel", "tsmc-arizona", "symbotic",
)
CUSTOMERS = NAMES[:3]
PROSPECTS = NAMES[3:]


def _runtime(tmp_path):
    # UI API-contract fix: use a task-local database, never a durable-commercial seed.
    url = f'sqlite:///{tmp_path / "ui-bands.db"}'
    engine = create_engine(url)
    metadata.create_all(engine)
    engine.dispose()
    return PocRuntime(Settings(_env_file=None, database_url=url, monitor_mode="disabled"))


def test_twelve_account_bands_and_sample_relationship_labels(tmp_path):
    runtime = _runtime(tmp_path)
    listed = {row["id"]: row for row in accounts(runtime)["accounts"] if row["id"] in NAMES}
    assert set(listed) == set(NAMES)
    for account_id in NAMES:
        # UI band fix: every applicable account family includes its existing scorer band.
        detail = account_360(account_id, runtime)
        fit = detail["prospect_fit"]
        if account_id in CUSTOMERS:
            assert detail["customer_health"]["band"] == detail["profile"]["health_band"]
            assert listed[account_id]["health_band"] == detail["profile"]["health_band"]
            assert detail["profile"]["internal_commercial_risk"]["band"]
            if account_id in {"lockheed-martin", "northrop-grumman"}:
                # UI safety fix: an authored ledger never confirms a real BTX relationship.
                label = detail["organization_360"]["relationship_label"]
                assert label == "SAMPLE customer (authored ledger)" and "Confirmed" not in label
        else:
            assert fit["score"] is not None and fit["band"] in {"STRONG", "RELEVANT", "LIMITED"}
            assert listed[account_id]["prospect_fit"]["band"] == fit["band"]
        # UI enum fix: machine state remains available, but the display label is plain language.
        public = detail["public_relationship"]
        if public:
            assert public["label"] == PUBLIC_RELATIONSHIP_LABELS[public["state"].value]
            assert public["label"] != public["state"]
    # UI safety fix: SAMPLE-classified customers without an authored ledger are not confirmed either.
    for account_id in ("spacex", "huxwrx"):
        label = account_360(account_id, runtime)["organization_360"]["relationship_label"]
        assert label == "SAMPLE customer (unverified relationship)"


def test_pursuit_scores_and_account_scoped_evidence(tmp_path):
    runtime = _runtime(tmp_path)
    rows = opportunity_workspace(Response(), actor=None, runtime=runtime)["opportunities"]
    scoped = {row["account_id"]: row for row in rows if row["account_id"] in NAMES}
    assert set(scoped) == set(NAMES[:9])
    for account_id, row in scoped.items():
        # UI pursuit-band fix: the API supplies numeric results and existing band/grade.
        for family in ("opportunity_priority", "pwin", "delivery_feasibility"):
            assert row[family]["score"] is not None and row[family]["band"]
        if account_id == "ge-aerospace":
            # UI evidence fix: a no-ledger pursuit resolves through its account-scoped read view.
            evidence = commercial_evidence(account_id, "evidence", Response(), record_id=row["source_record_id"],
                                           actor=None, runtime=runtime)
            assert evidence["kind"] == "opportunities"
            assert evidence["record"]["opportunity_id"] == row["opportunity_id"]
            # UI evidence fix: verify HTTP 200 and account-scope 404 through the real route.
            app = FastAPI()
            app.include_router(commercial_router)
            app.dependency_overrides[get_runtime] = lambda: runtime
            app.dependency_overrides[principal] = lambda: None
            client = TestClient(app)
            path = f"/accounts/{account_id}/commercial/evidence"
            response = client.get(path, params={"record_id": row["source_record_id"]})
            assert response.status_code == 200
            assert response.json()["record"]["opportunity_id"] == row["opportunity_id"]
            assert client.get("/accounts/blue-origin/commercial/evidence",
                              params={"record_id": row["source_record_id"]}).status_code == 404
    assert not any(row["account_id"] in NAMES[9:] for row in rows)
