import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.monitor.ontology import CandidateReviewState, ResolutionState
from btx_omni.monitor.sources import UsaSpendingAdapter
from btx_omni.persistence.models import metadata, monitor_program_candidates

_OPERATOR_HEADERS = {"X-BTX-Monitor-Operator-Token": "test-operator-token"}


def _runtime(tmp_path) -> PocRuntime:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_operator_token="test-operator-token",
        database_url=f"sqlite:///{tmp_path / 'program-candidate-promotion.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return PocRuntime(settings)


def _adapter() -> UsaSpendingAdapter:
    award = {
        "generated_internal_id": "CONT_AWD_PROGRAM_PROMOTION_9700_-NONE-_-NONE-",
        "Award ID": "PROGRAM-PROMOTION-1",
        "Recipient Name": "Nexus Quantum Systems, Inc.",
        "Award Amount": "250000",
        "Award Type": "D",
        "Description": "Semiconductor fabrication production support",
        "Program Name": "Aurora Fabrication Vehicle",
    }

    def post(url: str, _body: bytes, _headers: dict[str, str]):
        if url.endswith("transactions/"):
            return 200, json.dumps({"results": [{"action_date": "2026-08-10", "description": "Awarded semiconductor fabrication production support", "federal_action_obligation": "250000", "type": "D"}]}).encode(), {}
        return 200, json.dumps({"results": [award]}).encode(), {}

    return UsaSpendingAdapter(recipient_names=("Nexus Quantum Systems, Inc.",), post=post)


def _client(runtime: PocRuntime) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: runtime
    return TestClient(app)


def _candidates(runtime: PocRuntime):
    runtime.monitor.registry["usaspending"] = _adapter()
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert len(organizations) == len(programs) == 1
    return organizations[0], programs[0]


def test_confirmed_program_candidate_promotion_is_atomic_idempotent_and_runtime_visible(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    organization, candidate = _candidates(runtime)
    scoring_before = dict(runtime.sample.scoring_inputs)
    client = _client(runtime)
    assert runtime.monitor.catalog.resolve_program(candidate.source_name).state is ResolutionState.UNRESOLVED
    assert client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", json={"confirmed": True}).status_code == 403
    assert client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers={"X-BTX-Monitor-Operator-Token": "wrong"}, json={"confirmed": True}).status_code == 403
    assert runtime.monitor.catalog.resolve_program(candidate.source_name).state is ResolutionState.UNRESOLVED

    missing_confirmation = client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": False})
    assert missing_confirmation.status_code == 409
    assert runtime.monitor.catalog.resolve_program(candidate.source_name).state is ResolutionState.UNRESOLVED

    account_response = client.post(f"/api/monitor/candidates/{organization.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": True})
    assert account_response.status_code == 200
    nexus_id = account_response.json()["account"]["id"]

    response = client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": True})
    assert response.status_code == 200
    program_id = response.json()["program"]["id"]
    program = next(item for item in runtime.environment().programs if item.id == program_id)
    assert program.name == "Aurora Fabrication Vehicle"
    assert program.account_id == nexus_id
    assert runtime.monitor.catalog.resolve_program("Aurora Fabrication Vehicle production award").canonical_program_id == program_id
    assert runtime.sample.scoring_inputs == scoring_before
    assert not [item for item in runtime.sample.commercial_contexts if item.account_id == nexus_id]
    assert not [item for item in runtime.sample.public_facilities if item.account_id == nexus_id]

    runtime.monitor.collect("usaspending")
    event = next(iter(runtime.monitor.events.values()))
    assert event.program.canonical_program_id == program_id
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert organizations[0].id == organization.id
    assert programs[0].review_state is CandidateReviewState.PROMOTED
    assert programs[0].promoted_program_id == program_id

    repeat = client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": True})
    assert repeat.status_code == 200
    assert repeat.json()["created"] is False
    assert repeat.json()["program"]["id"] == program_id

    restarted = PocRuntime(runtime.settings)
    restored = next(item for item in restarted.environment().programs if item.id == program_id)
    assert restored == program
    restored_candidate = restarted.monitor.repository.candidates()[1][0]  # type: ignore[union-attr]
    assert restored_candidate.review_state is CandidateReviewState.PROMOTED
    assert restored_candidate.promoted_program_id == program_id
    assert restarted.monitor.catalog.resolve_program("Aurora Fabrication Vehicle").canonical_program_id == program_id


def test_program_candidate_promotion_rejects_terminal_and_insufficient_states(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    _organization, candidate = _candidates(runtime)
    client = _client(runtime)
    engine = runtime.monitor.repository.engine  # type: ignore[union-attr]

    for state in (CandidateReviewState.AMBIGUOUS, CandidateReviewState.REJECTED):
        with engine.begin() as connection:
            connection.execute(update(monitor_program_candidates).where(
                monitor_program_candidates.c.id == candidate.id
            ).values(review_state=state.value))
        assert client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": True}).status_code == 409

    with engine.begin() as connection:
        connection.execute(update(monitor_program_candidates).where(
            monitor_program_candidates.c.id == candidate.id
        ).values(review_state=CandidateReviewState.PENDING_REVIEW.value, source_name=""))
    assert client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", headers=_OPERATOR_HEADERS, json={"confirmed": True}).status_code == 409
