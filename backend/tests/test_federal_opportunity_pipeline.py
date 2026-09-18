import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine

from btx_omni.api.actions import CreateAction
from btx_omni.api.actions import create as create_action
from btx_omni.core.config import Settings
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.domain.work import ActionPriority, Principal, PrincipalRole
from btx_omni.modules.assistant.orchestration import OmniResponse
from btx_omni.modules.assistant.service import OmniService
from btx_omni.modules.federal_opportunity_routing import (
    build_assessment,
    procurement_stage,
    route_opportunity,
)
from btx_omni.modules.work.service import WorkService
from btx_omni.monitor.procurement import CoverageState
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.sources import SamAdapter, UsaSpendingAdapter
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 9, 16, tzinfo=UTC)


def settings(**updates):
    values = {
        "sam_api_key": "test-key", "monitor_mode": "live",
        "monitor_durable_state_enabled": True, "monitor_sam_naics": "336412",
        "monitor_sam_naics_verification_state": "VERIFIED",
        "monitor_sam_request_budget": 1, "monitor_sam_page_size": 2,
        **updates,
    }
    return Settings(_env_file=None, **values)


def test_sam_continues_beyond_one_run_budget_and_captures_later_record() -> None:
    calls = []

    def get(url, _headers):
        calls.append(url)
        offset = int(url.split("offset=")[1].split("&")[0])
        records = [
            {"noticeId": f"N-{index}", "title": f"Record {index}", "naicsCode": "336412"}
            for index in range(offset, min(offset + 2, 5))
        ]
        return 200, json.dumps({"totalRecords": 5, "opportunitiesData": records}).encode(), {}

    adapter = SamAdapter(get)
    checkpoints = ()
    captured = []
    for run in range(3):
        result = adapter.collect_resumable(
            run_id=f"run-{run}", settings=settings(), checkpoints=checkpoints,
            collected_at=NOW,
        )
        captured.extend(item.source_identity.source_record_id for item in result.observations)
        checkpoints = result.checkpoints

    assert captured == ["N-0", "N-1", "N-2", "N-3", "N-4"]
    assert checkpoints[0].coverage_state is CoverageState.COMPLETE
    assert checkpoints[0].offset == 5
    assert len(calls) == 3


def test_sam_keeps_independent_naics_cursors_and_preserves_failed_cursor() -> None:
    calls = []

    def get(url, _headers):
        calls.append(url)
        if "ncode=336412" in url:
            return 429, b"{}", {}
        return 200, json.dumps({"totalRecords": 1, "opportunitiesData": [{"noticeId": "OK", "title": "OK"}]}).encode(), {}

    configured = settings(
        monitor_sam_naics="336411,336412",
        monitor_sam_request_budget=2,
    )
    result = SamAdapter(get).collect_resumable(
        run_id="run", settings=configured, checkpoints=(), collected_at=NOW,
    )
    by_key = {item.query_key: item for item in result.checkpoints}
    assert by_key["naics:336411"].coverage_state is CoverageState.COMPLETE
    assert by_key["naics:336412"].coverage_state is CoverageState.RATE_LIMITED
    assert by_key["naics:336412"].offset == 0
    assert by_key["naics:336412"].next_retry_at > NOW


def test_completed_naics_waits_for_siblings_before_overlapping_window_rolls() -> None:
    configured = settings(
        monitor_sam_naics="336411,336412", monitor_sam_request_budget=1
    )

    def get(url, _headers):
        code = "336411" if "ncode=336411" in url else "336412"
        return 200, json.dumps({"totalRecords": 1, "opportunitiesData": [{"noticeId": code, "title": code}]}).encode(), {}

    adapter = SamAdapter(get)
    first = adapter.collect_resumable(
        run_id="first", settings=configured, checkpoints=(), collected_at=NOW
    )
    second = adapter.collect_resumable(
        run_id="second", settings=configured, checkpoints=first.checkpoints,
        collected_at=NOW,
    )
    assert all(item.coverage_state is CoverageState.COMPLETE for item in second.checkpoints)
    third = adapter.collect_resumable(
        run_id="third", settings=configured, checkpoints=second.checkpoints,
        collected_at=NOW,
    )
    assert sum(item.coverage_state is CoverageState.COMPLETE for item in third.checkpoints) == 1
    assert sum(item.coverage_state is CoverageState.AWAITING_CONTINUATION for item in third.checkpoints) == 1


def test_checkpoint_and_assessment_round_trip_is_replay_safe(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'federal.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    result = SamAdapter(lambda _url, _headers: (200, json.dumps({"totalRecords": 0, "opportunitiesData": []}).encode(), {})).collect_resumable(
        run_id="run", settings=settings(), checkpoints=(), collected_at=NOW,
    )
    repository.persist_procurement_checkpoints(result.checkpoints)
    assert repository.procurement_coverage()[0]["coverage_state"] == "COMPLETE"
    projection = {"opportunity_id": "notice-1", "source_revision": "source-v1", "input_revision": "input-v1", "routes": []}
    first = repository.persist_federal_assessment(projection, now=NOW)
    replay = repository.persist_federal_assessment(projection, now=NOW)
    changed = repository.persist_federal_assessment({**projection, "input_revision": "input-v2"}, now=NOW)
    assert first["version"] == replay["version"] == 1
    assert changed["version"] == 2
    assert len(repository.current_federal_assessments()) == 1
    assert repository.federal_assessment_by_id(changed["id"], version=2)["input_revision"] == "input-v2"


def test_concurrent_assessment_replay_creates_one_current_version(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'federal-concurrent.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    projection = {
        "opportunity_id": "notice-concurrent",
        "source_revision": "source-v1",
        "input_revision": "input-v1",
    }
    with ThreadPoolExecutor(max_workers=4) as workers:
        rows = tuple(workers.map(lambda _: repository.persist_federal_assessment(projection, now=NOW), range(8)))
    assert {row["id"] for row in rows} == {rows[0]["id"]}
    assert {row["version"] for row in rows} == {1}
    assert len(repository.current_federal_assessments()) == 1


def test_usaspending_recipient_pages_resume_without_starving_other_targets() -> None:
    calls = []

    def post(url, body, _headers):
        request = json.loads(body)
        if url.endswith("/transactions/"):
            return 200, json.dumps({"results": []}).encode(), {}
        calls.append(request)
        recipient = request["filters"]["recipient_search_text"][0]
        page = request["page"]
        return 200, json.dumps({
            "results": [{
                "generated_internal_id": f"{recipient}-{page}",
                "Award ID": f"award-{recipient}-{page}",
                "Recipient Name": recipient,
                "Award Amount": 100,
                "Description": "precision machining",
            }],
            "page_metadata": {"hasNext": page == 1, "total": 2},
        }).encode(), {}

    configured = settings(
        monitor_usaspending_request_budget=1,
        monitor_usaspending_page_size=1,
    )
    adapter = UsaSpendingAdapter(
        recipient_names=("Existing Customer", "Qualified Partner"), post=post
    )
    checkpoints = ()
    for run in range(4):
        result = adapter.collect_resumable(
            run_id=f"usa-{run}", settings=configured,
            checkpoints=checkpoints, collected_at=NOW,
        )
        checkpoints = result.checkpoints
    assert all(item.coverage_state is CoverageState.COMPLETE for item in checkpoints)
    assert {item.query_value for item in checkpoints} == {
        "Existing Customer", "Qualified Partner"
    }
    assert len(calls) == 4


def _environment():
    customer = SimpleNamespace(id="customer", legal_name="Existing Customer", relationship=AccountRelationship.CURRENT_CUSTOMER, public_identity=None)
    partner = SimpleNamespace(id="partner", legal_name="Qualified Partner", relationship=AccountRelationship.PROSPECT, public_identity=None)
    prospect = SimpleNamespace(id="prospect", legal_name="New Prime", relationship=AccountRelationship.PROSPECT, public_identity=None)
    return SimpleNamespace(
        accounts=(customer, partner, prospect),
        programs=(SimpleNamespace(id="program", account_id="customer", name="TF33", system="Engine"),),
        capabilities=(SimpleNamespace(id="cap", name="Precision machining", description="machined aerospace housings", processes=("machining",), business_units=("BU-A",)),),
    )


def _opportunity(text: str, stage: str = "Sources Sought"):
    return {
        "canonical_source_id": "obs-1", "opportunity_id": "notice-1",
        "title": text, "description": text, "stage": procurement_stage(stage),
        "source_payload": {"title": text, "description": text, "type": stage},
        "source_revision": "revision-1",
    }


def test_routes_cover_direct_customer_partner_prospect_and_watch_without_claiming_participation() -> None:
    environment = _environment()
    opportunity = _opportunity("TF33 precision machining requirement with Qualified Partner and New Prime")
    opportunity["technical"] = {"program_or_platform": "TF33", "part_number": None}
    opportunity["durability"] = {"state": "ONE_TIME_OR_UNKNOWN"}
    routes = route_opportunity(opportunity, environment=environment, partnerships={"partner"})
    assert {item["route_type"] for item in routes} == {"DIRECT_BTX", "CUSTOMER_EXPANSION", "STRATEGIC_PARTNER", "NEW_PROSPECT", "MARKET_WATCH"}
    assert all(item["evidence_state"] != "CONFIRMED_PARTICIPATION" for item in routes)
    assert "validate" in next(item for item in routes if item["route_type"] == "CUSTOMER_EXPANSION")["governed_action"].casefold()


def test_sources_sought_stage_and_durability_remain_conservative() -> None:
    assessment = build_assessment(
        _opportunity("Precision machining Sources Sought; NSN 2840-00-863-4330RV; quantity 12"),
        environment=_environment(), awards=[], partnerships=set(), now=NOW,
    )
    assert assessment["stage"]["code"] == "SOURCES_SOUGHT"
    assert "not an open bid" in assessment["stage"]["explanation"]
    assert assessment["durability"]["state"] == "ONE_TIME_OR_UNKNOWN"
    assert assessment["technical"]["nsn"] == "2840-00-863-4330RV"
    assert assessment["technical"]["estimated_quantity"] == "12"


def _persisted_cross_surface_context(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'federal-context.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    assessment = build_assessment(
        {
            **_opportunity("Existing Customer TF33 precision machining Sources Sought"),
            "official_source_url": "https://sam.gov/opp/notice-1/view",
            "posted_date": NOW.date().isoformat(),
            "agency": "Department of Defense",
        },
        environment=_environment(), awards=[], partnerships=set(), now=NOW,
    )
    row = repository.persist_federal_assessment(assessment, now=NOW)
    route = next(item for item in assessment["routes"] if item["route_type"] == "CUSTOMER_EXPANSION")
    return repository, row, route


def test_federal_action_preserves_current_assessment_and_replays_idempotently(tmp_path) -> None:
    repository, row, route = _persisted_cross_surface_context(tmp_path)
    runtime = SimpleNamespace(
        monitor=SimpleNamespace(repository=repository),
        work=WorkService(),
        environment=lambda: _environment(),
        observed_at=lambda: NOW,
    )
    principal = Principal("seller", "Seller", PrincipalRole.SALESPERSON)
    body = CreateAction(
        account_id="customer", title=route["governed_action"],
        description="Review the governed federal route.",
        priority=ActionPriority.MEDIUM,
        evidence_ids=(row["id"], "obs-1"),
        context_referents=(
            ("federal_opportunity", row["opportunity_id"]),
            ("federal_assessment", row["id"]),
            ("federal_assessment_version", "1"),
            ("federal_route_type", "CUSTOMER_EXPANSION"),
        ),
        idempotency_key="federal-route-replay",
    )
    first = create_action(body, runtime, principal)
    replay = create_action(body, runtime, principal)
    assert first.id == replay.id
    assert dict(first.context_referents)["federal_assessment"] == row["id"]
    with pytest.raises(HTTPException, match="does not support"):
        create_action(body.model_copy(update={"account_id": "prospect"}), runtime, principal)


def test_omni_federal_context_keeps_stage_action_identity_and_source(tmp_path) -> None:
    _repository, row, route = _persisted_cross_surface_context(tmp_path)
    projection = {
        **row["projection"],
        "assessment_id": row["id"],
        "assessment_version": row["version"],
        "selected_route": route,
        "selected_account_id": "customer",
        "selected_partnership_id": None,
    }
    base = OmniResponse("base", "customer", (), (), (), None)
    answer = OmniService._federal_opportunity_answer(base, projection)
    assert "not an open bid" in answer.content
    assert answer.recommended_action == route["governed_action"]
    assert answer.context_used["federal_assessment_id"] == row["id"]
    assert answer.conversation_referent["opportunity_id"] == "notice-1"
    assert answer.citation_links[0].url == "https://sam.gov/opp/notice-1/view"
    assert "contract value" not in answer.content.casefold()
