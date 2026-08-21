"""Phase 9C.10 acceptance coverage for the governed Monitor discovery lifecycle."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.modules.scoring.account_attractiveness import (
    AccountAttractivenessInputs,
    calculate_account_attractiveness,
)
from btx_omni.monitor.ontology import CandidateReviewState, ResolutionState
from btx_omni.monitor.sources import FdaAdapter, UsaSpendingAdapter
from btx_omni.persistence.models import metadata


def _runtime(tmp_path) -> PocRuntime:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'phase-9c10-acceptance.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return PocRuntime(settings)


def _client(runtime: PocRuntime) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: runtime
    return TestClient(app)


def _fda(record_id: str) -> FdaAdapter:
    def get(_url: str, _headers: dict[str, str]):
        return 200, json.dumps({"results": [{"k_number": record_id, "device_name": "Medtronic device approval", "decision_date": "2026-08-15"}]}).encode(), {}
    return FdaAdapter(get)


def _nexus(record_id: str) -> UsaSpendingAdapter:
    award = {
        "generated_internal_id": f"CONT_AWD_{record_id}_-NONE-_-NONE-",
        "Award ID": record_id,
        "Recipient Name": "Nexus Quantum Systems, Inc.",
        "Award Amount": "250000",
        "Award Type": "D",
        "Description": "Semiconductor fabrication production support",
        "Program Name": "Aurora Fabrication Vehicle",
    }

    def post(url: str, _body: bytes, _headers: dict[str, str]):
        if url.endswith("transactions/"):
            body = {"results": [{"action_date": "2026-08-10", "description": "Awarded semiconductor fabrication production support", "federal_action_obligation": "250000", "type": "D"}]}
        else:
            body = {"results": [award]}
        return 200, json.dumps(body).encode(), {}

    return UsaSpendingAdapter(recipient_names=("Nexus Quantum Systems, Inc.",), post=post)


def _live_signals(runtime: PocRuntime) -> list[dict]:
    return [item for item in intelligence_signals(runtime) if item.get("data_mode") == "CONNECTED"]


def test_existing_account_monitor_enrichment_is_durable_idempotent_and_seller_visible(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    client = _client(runtime)
    commercial_before = tuple((item.account_id, item.ttm_revenue_minor, item.ttm_bookings_minor) for item in runtime.sample.commercial_contexts)
    score_before = calculate_account_attractiveness(AccountAttractivenessInputs(runtime.sample.scoring_inputs["medtronic"]), evidence_ids=("medtronic-public-identity",), calculated_at=runtime.observed_at()).score

    runtime.monitor.registry["fda_openfda"] = _fda("K-9C10-MEDTRONIC")
    runtime.monitor.collect("fda_openfda")
    event = next(item for item in runtime.monitor.events.values() if item.provenance.source_record_id == "K-9C10-MEDTRONIC")
    assert event.resolution_state is ResolutionState.RESOLVED
    assert event.subject_entities[0].canonical_account_id == "medtronic"
    assert event.seller_relevance_state.value == "RESOLVED_ELIGIBLE"

    signals_before = _live_signals(runtime)
    assert [item["id"] for item in signals_before] == [event.id]
    assert client.get("/api/intelligence").json()["signals"][-1]["id"] == event.id
    detail = client.get("/api/accounts/medtronic").json()
    assert any(item["id"] == event.id for item in detail["intelligence"])
    omni = client.post("/api/omni", json={"question": "What does this event mean?", "context": {"surface": "INTELLIGENCE", "selected_event_id": event.id}})
    assert omni.status_code == 200 and omni.json()["context_used"] == {"event_id": event.id, "surface": "INTELLIGENCE", "account_id": "medtronic"}

    runtime.monitor.collect("fda_openfda")
    assert [item["id"] for item in _live_signals(runtime)] == [event.id]
    restarted = PocRuntime(runtime.settings)
    restored = _live_signals(restarted)
    assert [item["id"] for item in restored] == [event.id]
    assert restored[0]["provenance"].source_record_id == "K-9C10-MEDTRONIC"
    score_after = calculate_account_attractiveness(AccountAttractivenessInputs(restarted.sample.scoring_inputs["medtronic"]), evidence_ids=("medtronic-public-identity",), calculated_at=restarted.observed_at()).score
    assert score_after == score_before
    assert tuple((item.account_id, item.ttm_revenue_minor, item.ttm_bookings_minor) for item in restarted.sample.commercial_contexts) == commercial_before


def test_net_new_monitor_discovery_requires_governed_promotions_and_rehydrates(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    client = _client(runtime)
    scoring_before = dict(runtime.sample.scoring_inputs)
    runtime.monitor.registry["usaspending"] = _nexus("9C10-NEXUS-1")
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert len(organizations) == len(programs) == 1
    organization, candidate = organizations[0], programs[0]
    assert organization.review_state is CandidateReviewState.PENDING_REVIEW
    assert candidate.review_state is CandidateReviewState.PENDING_REVIEW
    assert not any(account.legal_name == "Nexus Quantum Systems, Inc." for account in runtime.environment().accounts)
    assert client.post(f"/api/monitor/candidates/{organization.id}/promote", json={"confirmed": False}).status_code == 409

    account_promotion = client.post(f"/api/monitor/candidates/{organization.id}/promote", json={"confirmed": True})
    assert account_promotion.status_code == 200
    nexus_id = account_promotion.json()["account"]["id"]
    account = client.get(f"/api/accounts/{nexus_id}").json()
    assert account["account"]["relationship"] == "PROSPECT"
    assert account["account_attractiveness"]["score"] is None
    assert not account["prism_commercial_context"] and not account["public_facilities"]
    assert client.post("/api/omni", json={"question": "What is this account?", "context": {"surface": "ACCOUNT_DETAIL", "selected_account_id": nexus_id}}).status_code == 200
    assert not any(point["account_id"] == nexus_id for point in client.get("/api/map").json()["accounts"])

    program_promotion = client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", json={"confirmed": True})
    assert program_promotion.status_code == 200
    program_id = program_promotion.json()["program"]["id"]
    assert runtime.monitor.catalog.resolve_program("Aurora Fabrication Vehicle").canonical_program_id == program_id
    assert client.post(f"/api/monitor/candidates/{organization.id}/promote", json={"confirmed": True}).json()["created"] is False
    assert client.post(f"/api/monitor/program-candidates/{candidate.id}/promote", json={"confirmed": True}).json()["created"] is False

    runtime.monitor.registry["usaspending"] = _nexus("9C10-NEXUS-2")
    runtime.monitor.collect("usaspending")
    subsequent = next(item for item in runtime.monitor.events.values() if item.provenance.source_record_id == "CONT_AWD_9C10-NEXUS-2_-NONE-_-NONE-")
    assert subsequent.subject_entities[0].canonical_account_id == nexus_id
    assert subsequent.program.canonical_program_id == program_id
    organizations_after, programs_after = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert len(organizations_after) == len(programs_after) == 1
    assert organizations_after[0].review_state is CandidateReviewState.PROMOTED
    assert programs_after[0].review_state is CandidateReviewState.PROMOTED
    assert runtime.sample.scoring_inputs == scoring_before

    restarted = PocRuntime(runtime.settings)
    assert next(item for item in restarted.environment().accounts if item.id == nexus_id).relationship == "PROSPECT"
    assert restarted.monitor.catalog.resolve_program("Aurora Fabrication Vehicle").canonical_program_id == program_id
    restored_org, restored_program = restarted.monitor.repository.candidates()  # type: ignore[union-attr]
    assert restored_org[0].promoted_account_id == nexus_id
    assert restored_program[0].promoted_program_id == program_id
    assert [item["id"] for item in _live_signals(restarted)] == [subsequent.id]
    assert restarted.sample.scoring_inputs == scoring_before
