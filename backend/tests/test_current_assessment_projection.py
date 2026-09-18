import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, insert, select

from btx_omni.api.accounts import account_360
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.map import map_data
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.today import today
from btx_omni.core.config import Settings
from btx_omni.monitor.briefs import signal_briefs_for_monitor
from btx_omni.monitor.documents import canonical_public_evidence
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.sources import CompanyNewsAdapter
from btx_omni.persistence.models import (
    metadata,
    monitor_events,
    monitor_intelligence_assessments,
)

NOW = datetime(2026, 9, 16, 12, tzinfo=UTC)
LOCKHEED_SOURCE = "https://news.lockheedmartin.com/2026-08-30-Javelin"


def test_canonical_evidence_keeps_distinct_revisions_and_merges_best_metadata():
    rows = canonical_public_evidence(
        [
            {
                "evidence_id": "reviewed",
                "title": "Official release",
                "url": LOCKHEED_SOURCE,
                "provenance": "Lockheed Martin|2026-08-30|REVIEWED|partial",
            },
            {
                "evidence_id": "passage-one",
                "title": "Official release",
                "url": LOCKHEED_SOURCE + "#one",
                "provenance": json.dumps(
                    {"research_lineage": {"source_revision": "a" * 64}}
                ),
            },
            {
                "evidence_id": "passage-two",
                "title": "Official release, corrected",
                "url": LOCKHEED_SOURCE + "#two",
                "provenance": json.dumps(
                    {"research_lineage": {"source_revision": "b" * 64}}
                ),
            },
        ]
    )

    assert (
        len(rows) == 3
    )  # revisionless reviewed metadata cannot choose between two revisions
    assert any(item["publication_date"] == "2026-08-30" for item in rows)
    assert {item["source_revision"] for item in rows if item["source_revision"]} == {
        "a" * 64,
        "b" * 64,
    }


def _projection(
    *,
    priority: bool,
    relevance: str,
    evidence: bool = True,
    facility: dict | None = None,
    analysis_status: str | None = None,
) -> dict:
    public = (
        [
            {
                "evidence_id": "reviewed-lockheed",
                "title": "Lockheed Javelin co-production agreement",
                "source_url": LOCKHEED_SOURCE,
                "publication_date": "2026-08-30",
                "provenance": "Lockheed Martin|2026-08-30|REVIEWED|partial",
            },
            {
                "evidence_id": "passage-lockheed-1",
                "title": "Lockheed Javelin co-production agreement",
                "source_url": LOCKHEED_SOURCE + "#passage-1",
                "publication_date": None,
                "retrieved_at": "2026-09-15T10:00:00+00:00",
                "provenance": json.dumps(
                    {"research_lineage": {"source_revision": "a" * 64}}
                ),
            },
        ]
        if evidence
        else []
    )
    return {
        "headline": "Lockheed Martin Javelin co-production agreement",
        "analysis_status": analysis_status or ("READY" if evidence else "INCOMPLETE"),
        "commercial_relevance_state": relevance,
        "priority_eligible": priority,
        "recommended_action": (
            "Verify internal Lockheed and RTX records for Javelin activity."
            if priority
            or relevance in {"ESTABLISHED_ACCOUNT_REVIEW", "REVIEW_REQUIRED"}
            else None
        ),
        "evidence_package": {
            "public_evidence": public,
            "facility": facility,
            "deterministic_scores": {"signal_confidence": {"score": 84.71}},
            "technical_decomposition": {
                "components": [{"name": "Round"}],
                "fit_hypotheses": [
                    {"component_name": f"Fit {index}"} for index in range(8)
                ],
                "citations": [
                    {
                        "evidence_id": item["evidence_id"],
                        "title": item["title"],
                        "url": item["source_url"],
                        "publication_date": item.get("publication_date"),
                        "provenance": item.get("provenance"),
                    }
                    for item in public
                ],
            },
        },
    }


def _insert_context(
    connection,
    *,
    event_id: str,
    created_at: datetime,
    projection: dict,
    seller_state: str = "RESOLVED_ELIGIBLE",
    account_id: str = "lockheed-martin",
    version: int = 1,
) -> None:
    connection.execute(
        insert(monitor_events).values(
            id=event_id,
            source_id="fixture",
            source_observation_id=f"observation-{event_id}",
            event_type="CONTRACT_AWARD",
            publication_date=created_at,
            collected_at=created_at,
            updated_at=created_at,
            resolution_state="RESOLVED",
            seller_relevance_state=seller_state,
            data_mode="CONNECTED",
            provenance_source_id=event_id,
            provenance_url=LOCKHEED_SOURCE,
            evidence_ids="[]",
            event_payload="{}",
        )
    )
    connection.execute(
        insert(monitor_intelligence_assessments).values(
            id=f"assessment-{event_id}",
            context_key=f"{event_id}|{account_id}|ALL_BUSINESS_UNITS",
            event_id=event_id,
            account_id=account_id,
            business_unit_id=None,
            input_revision=f"{version:064d}"[-64:],
            source_revision="a" * 64,
            version=version,
            is_current=True,
            projection=json.dumps(projection),
            generation_status="DETERMINISTIC_READY",
            provider=None,
            model=None,
            created_at=created_at,
        )
    )


def test_current_display_assessments_filter_and_rank_before_bound(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    metadata.create_all(engine)
    with engine.begin() as connection:
        _insert_context(
            connection,
            event_id="javelin",
            created_at=NOW - timedelta(days=10),
            projection=_projection(priority=False, relevance="REVIEW_REQUIRED"),
            seller_state="RESOLVED_ELIGIBLE",
            version=4,
        )
        for index in range(55):
            _insert_context(
                connection,
                event_id=f"newer-informational-{index:02d}",
                created_at=NOW - timedelta(minutes=index),
                projection=_projection(priority=False, relevance="INFORMATIONAL"),
            )
        _insert_context(
            connection,
            event_id="ineligible",
            created_at=NOW + timedelta(minutes=1),
            projection=_projection(
                priority=True, relevance="INCOMPLETE", evidence=False
            ),
            seller_state="REJECTED",
        )

    repository = MonitorRepository(engine)
    selected = repository.current_display_assessments(limit=50)
    javelin = next(item for item in selected if item["event_id"] == "javelin")

    assert len(selected) == 50
    assert javelin["event_id"] == "javelin"
    assert javelin["version"] == 4
    assert javelin["event_seller_relevance_state"] == "RESOLVED_ELIGIBLE"
    assert (
        javelin["projection"]["evidence_package"]["deterministic_scores"][
            "signal_confidence"
        ]["score"]
        == 84.71
    )
    assert (
        len(
            javelin["projection"]["evidence_package"]["technical_decomposition"][
                "fit_hypotheses"
            ]
        )
        == 8
    )
    assert len(javelin["projection"]["references"]) == 1
    assert javelin["projection"]["references"][0]["publication_date"] == "2026-08-30"
    assert "ineligible" not in {item["event_id"] for item in selected}
    assert any(
        item["projection"]["commercial_relevance_state"] == "INFORMATIONAL"
        and not item["projection"]["priority_eligible"]
        for item in selected
    )
    assert (
        repository.current_display_assessments(
            limit=1, account_ids=frozenset({"lockheed-martin"}), priority_only=True
        )
        == ()
    )
    engine.dispose()


def test_persisted_assessment_is_identical_across_bounded_product_reads(
    tmp_path, monkeypatch
):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr("btx_omni.monitor.briefs.datetime", FrozenDateTime)
    database_url = f"sqlite:///{tmp_path / 'cross-surface.db'}"
    setup_engine = create_engine(database_url)
    metadata.create_all(setup_engine)
    setup_engine.dispose()
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        monitor_company_feed_registry=json.dumps(
            [
                {
                    "id": "lockheed-fixture",
                    "canonical_account_id": "lockheed-martin",
                    "url": "https://fixture.test/feed",
                }
            ]
        ),
    )
    runtime = PocRuntime(settings)
    feed = {"body": b""}

    def get(url: str, _headers: dict[str, str]):
        if url == "https://fixture.test/feed":
            return 200, feed["body"], {}
        return (
            200,
            b"<html><body>Official public source.</body></html>",
            {"content-type": "text/html"},
        )

    runtime.monitor.registry["company_newsroom"] = CompanyNewsAdapter(get)
    runtime.monitor.clock = lambda: NOW
    event_ids = []
    for index in range(56):
        is_javelin = index == 0
        guid = "javelin" if is_javelin else f"informational-{index:02d}"
        title = (
            "Lockheed Martin Javelin co-production agreement"
            if is_javelin
            else f"Lockheed Martin manufacturing program informational update {index:02d}"
        )
        published = (
            "Sun, 30 Aug 2026 10:00:00 GMT"
            if is_javelin
            else "Wed, 16 Sep 2026 10:00:00 GMT"
        )
        feed["body"] = (
            "<rss><channel><item>"
            f"<guid>{guid}</guid><title>{title}</title>"
            f"<link>https://fixture.test/{guid}</link><pubDate>{published}</pubDate>"
            "</item></channel></rss>"
        ).encode()
        before = set(runtime.monitor.events)
        runtime.monitor.collect("company_newsroom", limit=1)
        event_id = next(iter(set(runtime.monitor.events) - before))
        event_ids.append(event_id)
        with runtime.monitor.repository.engine.begin() as connection:
            payload = json.loads(
                connection.execute(
                    select(monitor_events.c.event_payload).where(
                        monitor_events.c.id == event_id
                    )
                ).scalar_one()
            )
            event_seller_state = "REJECTED" if index == 3 else "RESOLVED_ELIGIBLE"
            payload["seller_relevance_state"] = event_seller_state
            connection.execute(
                monitor_events.update()
                .where(monitor_events.c.id == event_id)
                .values(
                    seller_relevance_state=event_seller_state,
                    event_payload=json.dumps(payload),
                )
            )
        if is_javelin:
            projection = _projection(priority=False, relevance="REVIEW_REQUIRED")
        elif index == 1:
            projection = _projection(
                priority=True, relevance="ESTABLISHED_COMMERCIAL_RELEVANCE"
            )
        elif index == 2:
            projection = _projection(
                priority=False,
                relevance="REVIEW_REQUIRED",
                evidence=False,
                analysis_status="READY",
            )
        else:
            projection = _projection(priority=False, relevance="INFORMATIONAL")
        if index == 55:
            projection["evidence_package"]["facility"] = {
                "id": "lockheed-orlando",
                "name": "Lockheed Martin Orlando",
            }
        versions = range(1, 5) if is_javelin else (1,)
        for version in versions:
            runtime.monitor.repository.save_intelligence_assessment(
                event_id=event_id,
                account_id="lockheed-martin",
                business_unit_id=None,
                input_revision=f"{index + 1:030d}{version:034d}"[-64:],
                source_revision="a" * 64,
                projection=projection,
                generation_status="DETERMINISTIC_READY",
                provider=None,
                model=None,
                created_at=NOW + timedelta(minutes=index, seconds=version),
            )
    javelin_event = event_ids[0]
    action_event = event_ids[1]
    insufficient_evidence_event = event_ids[2]
    ineligible_event = event_ids[3]

    selected = runtime.monitor.repository.current_display_assessments(limit=50)
    selected_javelin = next(
        item for item in selected if item["event_id"] == javelin_event
    )
    assert selected_javelin["projection"]["evidence_package"]["facility"] is None
    assert selected_javelin["event_seller_relevance_state"] == "RESOLVED_ELIGIBLE"
    assert insufficient_evidence_event not in {item["event_id"] for item in selected}
    assert ineligible_event not in {item["event_id"] for item in selected}
    assert any(
        item["projection"]["evidence_package"].get("facility")
        == {"id": "lockheed-orlando", "name": "Lockheed Martin Orlando"}
        for item in selected
    )
    briefs = signal_briefs_for_monitor(
        runtime.monitor,
        now=NOW,
        environment=runtime.environment(),
        projection_limit=50,
    )
    assert javelin_event in {item.id for item in briefs}
    action_brief = next(item for item in briefs if item.id == action_event)
    assert (
        action_brief.resolution_state,
        action_brief.seller_promotion_state,
        action_brief.analysis_status,
        action_brief.commercial_relevance_state,
        action_brief.priority_eligible,
        action_brief.freshness,
        action_brief.event_timing,
    ) == (
        "RESOLVED",
        "RESOLVED_ELIGIBLE",
        "READY",
        "ESTABLISHED_COMMERCIAL_RELEVANCE",
        True,
        "CURRENT",
        "OBSERVED",
    )
    intelligence = intelligence_signals(runtime)
    connected = [item for item in intelligence if item["id"] in set(event_ids)]
    javelin = next(item for item in connected if item["id"] == javelin_event)
    informational = next(item for item in connected if item["id"] == event_ids[55])
    assert (
        informational["business_briefing"]["commercial_relevance_state"]
        == "INFORMATIONAL"
    )
    assessment = javelin["business_briefing"]
    profile = account_360("lockheed-martin", runtime)
    profile_brief = next(
        item["business_briefing"]
        for item in profile["intelligence"]
        if item["id"] == javelin_event
    )
    map_projection = map_data(runtime=runtime)
    lockheed_point = next(
        item
        for item in map_projection["accounts"]
        if item["account_id"] == "lockheed-martin"
    )
    map_brief = next(
        item
        for item in lockheed_point["current_signal_briefs"]
        if item["id"] == javelin_event
    )
    today_projection = today(runtime)
    command_center = today_projection["command_center"]
    today_brief = next(
        item["signal_brief"]
        for item in command_center["needs_validation_assessments"]
        if item.get("event_id") == javelin_event
    )

    identities = {
        (item["assessment_id"], item["assessment_version"])
        for item in (assessment, profile_brief, map_brief, today_brief)
    }
    assert len(selected) == 50 and len(identities) == 1
    assert next(iter(identities))[1] == 4
    assert assessment["signal_confidence"]["score"] == 84.71
    assert len(assessment["technical_opportunity"]["fit_hypotheses"]) == 8
    assert assessment["seller_promotion_state"] == "RESOLVED_ELIGIBLE"
    assert assessment["commercial_relevance_state"] == "REVIEW_REQUIRED"
    assert assessment["priority_eligible"] is False
    assert assessment["recommended_action"].startswith("Verify internal Lockheed")
    assert not any(
        item["event_id"] == javelin_event for item in map_projection["intelligence"]
    )
    assert len(assessment["references"]) == 1
    assert assessment["references"][0]["publication_date"] == "2026-08-30"
    assert command_center["public_intelligence_counts"] == {
        "action_priorities": 1,
        "needs_validation": 1,
    }
    assert [item["event_id"] for item in command_center["action_priorities"]] == [
        action_event
    ]
    assert all(
        item["event_id"]
        not in {event_ids[55], insufficient_evidence_event, ineligible_event}
        for item in (
            *command_center["action_priorities"],
            *command_center["needs_validation_assessments"],
        )
    )
    with runtime.monitor.repository.engine.connect() as connection:
        assert (
            connection.execute(
                select(monitor_events.c.seller_relevance_state).where(
                    monitor_events.c.id == javelin_event
                )
            ).scalar_one()
            == "RESOLVED_ELIGIBLE"
        )
    runtime.monitor.repository.engine.dispose()
