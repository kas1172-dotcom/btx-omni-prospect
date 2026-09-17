import json
from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.config import Settings
from btx_omni.monitor.candidates import organization_candidate_for
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.normalization import normalize_structured_observation
from btx_omni.monitor.ontology import CandidateReviewState, ResolutionState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.monitor.sources import FdaAdapter, UsaSpendingAdapter
from btx_omni.persistence.models import metadata


def _runtime(tmp_path) -> PocRuntime:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'monitor-candidates.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return PocRuntime(settings)


def _award_adapter(*, recipient: str, program_name: str | None = None) -> UsaSpendingAdapter:
    award = {
        "generated_internal_id": "CONT_AWD_CANDIDATE_9700_-NONE-_-NONE-",
        "Award ID": "CANDIDATE-1",
        "Recipient Name": recipient,
        "Award Amount": "250000",
        "Award Type": "D",
    }
    if program_name:
        award["Program Name"] = program_name

    def post(url: str, _body: bytes, _headers: dict[str, str]):
        if url.endswith("transactions/"):
            return 200, json.dumps({"results": [{"action_date": "2026-08-10", "description": "Awarded production support", "federal_action_obligation": "250000", "type": "D"}]}).encode(), {}
        return 200, json.dumps({"results": [award]}).encode(), {}

    return UsaSpendingAdapter(recipient_names=(recipient,), post=post)


def _fda_observation():
    return FdaAdapter(
        lambda _url, _headers: (200, json.dumps({"results": [{"k_number": "K-CANDIDATE", "device_name": "Nexus Quantum Systems approval", "decision_date": "2026-08-15"}]}).encode(), {})
    ).collect(run_id="candidate", settings=Settings(_env_file=None, monitor_mode="live"))[0]


def test_net_new_organization_and_explicit_program_are_durable_review_candidates(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    scoring_inputs_before = dict(runtime.sample.scoring_inputs)
    runtime.monitor.registry["usaspending"] = _award_adapter(
        recipient="Nexus Quantum Systems, Inc.",
        program_name="Aurora Fabrication Vehicle",
    )
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]

    assert len(organizations) == len(programs) == 1
    organization, program = organizations[0], programs[0]
    assert organization.source_name == "Nexus Quantum Systems, Inc."
    assert organization.review_state is CandidateReviewState.PENDING_REVIEW
    assert organization.resolution_state is ResolutionState.UNRESOLVED
    assert organization.provenance.source_record_id == "CONT_AWD_CANDIDATE_9700_-NONE-_-NONE-"
    assert program.source_name == "Aurora Fabrication Vehicle"
    assert program.organization_candidate_id == organization.id
    assert program.canonical_account_id is None
    assert program.event_ids == organization.event_ids
    assert organization.id not in {account.id for account in runtime.sample.accounts}
    assert "Nexus Quantum Systems, Inc." not in {account.legal_name for account in runtime.sample.accounts}
    assert runtime.sample.scoring_inputs == scoring_inputs_before

    runtime.monitor.collect("usaspending")
    restarted = PocRuntime(runtime.settings)
    organizations_after, programs_after = restarted.monitor.repository.candidates()  # type: ignore[union-attr]
    assert [item.id for item in organizations_after] == [organization.id]
    assert [item.event_ids for item in organizations_after] == [organization.event_ids]
    assert [item.id for item in programs_after] == [program.id]
    assert restarted.sample.commercial_contexts
    assert restarted.sample.scoring_inputs == scoring_inputs_before

    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: restarted
    response = TestClient(app).get("/api/monitor/candidates", headers={"X-BTX-Principal-Token": "development-manager"})
    assert response.status_code == 200
    assert response.json()["organization_candidates"][0]["id"] == organization.id
    assert response.json()["program_candidates"][0]["organization_candidate_id"] == organization.id


def test_existing_account_and_exact_canonical_program_do_not_create_candidates(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    program_name = runtime.sample.programs[0].name
    runtime.monitor.registry["usaspending"] = _award_adapter(recipient="Medtronic", program_name=program_name)
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]

    assert organizations == programs == ()
    event = next(iter(runtime.monitor.events.values()))
    assert event.subject_entities[0].canonical_account_id == "medtronic"
    assert event.program.canonical_program_id == runtime.sample.programs[0].id


def test_generic_company_event_does_not_create_a_program_candidate(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    runtime.monitor.registry["usaspending"] = _award_adapter(recipient="Nexus Quantum Systems, Inc.")
    runtime.monitor.collect("usaspending")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]

    assert len(organizations) == 1
    assert programs == ()


def test_ambiguous_exact_alias_and_conflicting_identifiers_never_become_promotion_ready(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    profiles = (
        AccountWatchProfile("one", "Acme One", aliases=("Acme Systems",), source_native_identifiers=(("uei", "UEI-1"),)),
        AccountWatchProfile("two", "Acme Two", aliases=("Acme Systems",), source_native_identifiers=(("cage", "CAGE-2"),)),
    )
    runtime.monitor.registry["usaspending"] = _award_adapter(recipient="Acme Systems")
    runtime.monitor.watch_profiles = profiles
    runtime.monitor.catalog = MonitorCatalog(profiles, runtime.sample.programs, runtime.sample.facilities)
    runtime.monitor.collect("usaspending")
    organizations, _programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert len(organizations) == 1
    assert organizations[0].review_state is CandidateReviewState.AMBIGUOUS
    assert organizations[0].candidate_account_ids == ("one", "two")

    observation = _fda_observation()
    observation = replace(observation, source_identity=replace(observation.source_identity, source_native_ids=(("uei", "UEI-1"), ("cage", "CAGE-2"))))
    resolution = resolve_entity("Nexus Quantum Systems", profiles, source_identifiers=observation.source_identity.source_native_ids)
    event = normalize_structured_observation(observation, subject_mention="Nexus Quantum Systems", catalog=runtime.monitor.catalog).event
    candidate = organization_candidate_for(replace(event, subject_entities=(resolution,), resolution_state=resolution.state), observation)
    assert resolution.state is ResolutionState.AMBIGUOUS
    assert candidate and candidate.review_state is CandidateReviewState.AMBIGUOUS


def test_insufficient_identity_and_fuzzy_name_do_not_create_or_promote_candidate(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    runtime.monitor.registry["fda_openfda"] = FdaAdapter(
        lambda _url, _headers: (200, json.dumps({"results": [{"k_number": "K-UNKNOWN", "device_name": "Unknown device approval", "decision_date": "2026-08-15"}]}).encode(), {})
    )
    runtime.monitor.collect("fda_openfda")
    organizations, programs = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    assert organizations == programs == ()
    assert resolve_entity("Nexus Quantum", runtime.sample.watch_profiles).state is ResolutionState.UNRESOLVED
