import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.monitor.ontology import CandidateReviewState
from btx_omni.monitor.resolution import resolve_entity
from btx_omni.monitor.sources import UsaSpendingAdapter
from btx_omni.persistence.models import metadata, monitor_organization_candidates


def _runtime(tmp_path) -> PocRuntime:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'candidate-promotion.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return PocRuntime(settings)


def _adapter(recipient: str = "Nexus Quantum Systems, Inc.") -> UsaSpendingAdapter:
    award = {
        "generated_internal_id": "CONT_AWD_PROMOTION_9700_-NONE-_-NONE-",
        "Award ID": "PROMOTION-1",
        "Recipient Name": recipient,
        "Award Amount": "250000",
        "Award Type": "D",
        "Description": "Semiconductor fabrication production support",
        "Program Name": "Aurora Fabrication Vehicle",
    }

    def post(url: str, _body: bytes, _headers: dict[str, str]):
        if url.endswith("transactions/"):
            return 200, json.dumps({"results": [{"action_date": "2026-08-10", "description": "Awarded production support", "federal_action_obligation": "250000", "type": "D"}]}).encode(), {}
        return 200, json.dumps({"results": [award]}).encode(), {}

    return UsaSpendingAdapter(recipient_names=(recipient,), post=post)


def _client(runtime: PocRuntime) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: runtime
    return TestClient(app)


def _nexus_candidate(runtime: PocRuntime):
    runtime.monitor.registry["usaspending"] = _adapter()
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert len(organizations) == len(programs) == 1
    return organizations[0], programs[0]


def test_confirmed_candidate_promotion_is_atomic_idempotent_and_runtime_visible(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    candidate, program = _nexus_candidate(runtime)
    scoring_before = dict(runtime.sample.scoring_inputs)
    assert not [account for account in runtime.sample.accounts if account.legal_name == candidate.source_name]

    client = _client(runtime)
    missing_confirmation = client.post(f"/api/monitor/candidates/{candidate.id}/promote", json={"confirmed": False})
    assert missing_confirmation.status_code == 409
    assert not [account for account in runtime.sample.accounts if account.legal_name == candidate.source_name]

    response = client.post(f"/api/monitor/candidates/{candidate.id}/promote", json={"confirmed": True})
    assert response.status_code == 200
    account_id = response.json()["account"]["id"]
    account = next(item for item in runtime.environment().accounts if item.id == account_id)
    assert account.relationship is AccountRelationship.PROSPECT
    assert account_id not in runtime.sample.scoring_inputs
    assert not [item for item in runtime.sample.commercial_contexts if item.account_id == account_id]
    assert not [item for item in runtime.sample.public_facilities if item.account_id == account_id]
    assert runtime.sample.scoring_inputs == scoring_before
    assert resolve_entity("Nexus Quantum Systems, Inc.", runtime.sample.watch_profiles).canonical_account_id == account_id
    assert resolve_entity("Nexus Quantum Systems, Inc.", runtime.monitor.catalog.profiles).canonical_account_id == account_id

    listed = client.get("/api/accounts")
    detail = client.get(f"/api/accounts/{account_id}")
    omni = client.post("/api/omni", json={"question": "Does it have quote history?", "context": {"surface": "ACCOUNT_DETAIL", "selected_account_id": account_id}})
    assert listed.status_code == detail.status_code == omni.status_code == 200
    listed_account = next(item for item in listed.json()["accounts"] if item["id"] == account_id)
    assert listed_account["attractiveness"] is None
    assert detail.json()["account_attractiveness"]["score"] is None
    assert omni.json()["context_used"]["account_id"] == account_id

    repeat = client.post(f"/api/monitor/candidates/{candidate.id}/promote", json={"confirmed": True})
    assert repeat.status_code == 200
    assert repeat.json()["created"] is False
    assert repeat.json()["account"]["id"] == account_id
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert organizations[0].review_state is CandidateReviewState.PROMOTED
    assert organizations[0].promoted_account_id == account_id
    assert programs[0].id == program.id
    assert programs[0].organization_candidate_id == candidate.id

    restarted = PocRuntime(runtime.settings)
    promoted, restarted_programs = restarted.monitor.repository.candidates()  # type: ignore[union-attr]
    assert promoted[0].review_state is CandidateReviewState.PROMOTED
    assert promoted[0].promoted_account_id == account_id
    assert restarted_programs[0].id == program.id
    assert sum(account.id == account_id for account in restarted.environment().accounts) == 1
    assert resolve_entity("Nexus Quantum Systems, Inc.", restarted.sample.watch_profiles).canonical_account_id == account_id


def test_candidate_promotion_rejects_terminal_and_conflicted_identity_states(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    candidate, _program = _nexus_candidate(runtime)
    client = _client(runtime)
    engine = runtime.monitor.repository.engine  # type: ignore[union-attr]

    for state in (CandidateReviewState.AMBIGUOUS, CandidateReviewState.REJECTED):
        with engine.begin() as connection:
            connection.execute(update(monitor_organization_candidates).where(
                monitor_organization_candidates.c.id == candidate.id
            ).values(review_state=state.value))
        response = client.post(f"/api/monitor/candidates/{candidate.id}/promote", json={"confirmed": True})
        assert response.status_code == 409
