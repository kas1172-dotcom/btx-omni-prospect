from dataclasses import replace
from datetime import UTC, datetime
from random import Random
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_command_center import NOW, brief, projection

from btx_omni.api import today as today_api
from btx_omni.domain.alerts import CommercialAlert, CommercialAlertKind
from btx_omni.modules.priority_ordering import (
    EXCLUDED,
    INTERNAL_NATURE,
    PUBLIC_NATURE,
    PriorityMetadata,
    order_priorities,
    priority_candidate,
)
from btx_omni.monitor.ontology import EventType


def internal(item_id, *, severity="HIGH", kind="BOOKINGS_DECLINE", **fields):
    values = {
        "id": item_id,
        "type": kind,
        "status": "OPEN",
        "severity": severity,
        "account_id": "acct-1",
        "evidence_ids": ("internal-evidence",),
        "observed_at": NOW,
        "trigger_reason": "Source reason",
        "recommended_action": "Review",
        "provenance_state": "CONFIRMED",
    }
    return SimpleNamespace(**(values | fields))


def public(item_id, *, risk=None, opportunity=None, confidence=80, **fields):
    values = {
        "event_type": "PRODUCTION_DELAY" if risk else "FACILITY_EXPANSION",
        "risk_severity": risk,
        "signal_confidence": {"score": confidence},
        "evidence_package": {
            "deterministic_scores": {"opportunity_priority": opportunity}
        },
    }
    return replace(brief(item_id, event_at=NOW), **(values | fields))


def test_escalate_now_beats_higher_opportunity_and_sources_interleave():
    result = projection(
        public("public-risk", risk={"score": 90}),
        public("public-opportunity", opportunity={"score": 99}),
        alerts=(
            internal("internal-risk", risk_severity={"score": 80}),
            internal(
                "internal-followup",
                kind="QUOTE_FOLLOW_UP",
                opportunity_priority={"score": 85},
            ),
        ),
    )
    rows = result["priority_briefing"]
    assert [row["id"] for row in rows] == [
        "public-risk",
        "internal-risk",
        "public-opportunity",
        "internal-followup",
    ]
    assert [row["triage_class"] for row in rows] == [1, 1, 3, 3]
    assert all(row["high_importance"] for row in rows)
    assert rows[1]["alert_kind"] == "BOOKINGS_DECLINE"
    assert rows[1]["status"] == "OPEN"
    assert "status" not in rows[0] and "alert_kind" not in rows[0]


def test_complete_precedes_incomplete_in_same_class_and_ranges_use_ceiling():
    rows = projection(
        public(
            "partial",
            opportunity={"score": None, "score_range": {"low": 20, "high": 99}},
        ),
        public("complete", opportunity={"score": 30}),
        public(
            "lower-ceiling",
            opportunity={"score": None, "score_range": {"low": 50, "high": 80}},
        ),
    )["priority_briefing"]
    assert [row["id"] for row in rows] == ["complete", "partial", "lower-ceiling"]
    assert [row["assessment_complete"] for row in rows] == [True, False, False]
    assert rows[1]["underlying_score"] == 99
    assert rows[1]["score_kind"] == "OPPORTUNITY_PRIORITY"
    assert rows[1]["high_importance"] is False


def test_100_seeded_shuffles_produce_identical_order_and_metadata():
    rng = Random(421)
    sources = [
        public("p-risk", risk={"score": 90}),
        public("p-low", opportunity={"score": 25}),
        public("p-mid", opportunity={"score": 50}),
        public("p-unknown", event_type=None),
        public("p-partial", opportunity={"score_range": {"low": 20, "high": 90}}),
    ]
    alerts = [
        internal("i-high"),
        internal("i-low", severity="LOW"),
        internal("i-stop", hard_stop=True),
        internal("i-closed", status="COMPLETED"),
        internal("i-tie-b", severity="LOW"),
        internal("i-tie-a", severity="LOW"),
    ]
    expected = projection(*sources, alerts=tuple(alerts))["priority_briefing"]
    for _ in range(100):
        rng.shuffle(sources)
        rng.shuffle(alerts)
        assert (
            projection(*sources, alerts=tuple(alerts))["priority_briefing"] == expected
        )


def test_unknown_nature_and_unknown_confidence_do_not_escalate():
    rows = projection(
        public(
            "unknown",
            event_type="UNCLASSIFIED_PUBLIC_UPDATE",
            opportunity={"score": 100},
        ),
        public("risk-unknown-confidence", risk={"score": 90}, confidence=None),
    )["priority_briefing"]
    by_id = {row["id"]: row for row in rows}
    assert all(row["triage_class"] == 3 for row in rows)
    assert by_id["unknown"]["nature"] == "UNKNOWN"
    assert by_id["unknown"]["high_importance"] is False
    # Explicit user rule: a Class 3 risk can still be high importance.
    assert by_id["risk-unknown-confidence"]["high_importance"] is True
    assert by_id["risk-unknown-confidence"]["assessment_complete"] is False


@pytest.mark.parametrize(
    "confidence,expected", [(70, 1), (69.99, 2), (40, 2), (0, 2), (None, 3)]
)
def test_risk_confidence_boundaries(confidence, expected):
    row = projection(public("risk", risk={"score": 70}, confidence=confidence))[
        "priority_briefing"
    ][0]
    assert row["triage_class"] == expected


@pytest.mark.parametrize("status", sorted(EXCLUDED))
def test_all_closed_states_excluded_before_ranking(status):
    result = projection(alerts=(internal("closed", status=status, hard_stop=True),))
    assert result["priority_briefing"] == ()
    assert result["daily_briefing"]["commercial_attention_count"] == 0


def test_flags_invalid_duplicate_and_explicit_hard_stop():
    rows = projection(
        alerts=(
            internal("stop", hard_stop=True),
            internal("stop", hard_stop=True),
            internal("overdue", kind="OVERDUE_ORDER"),
            internal("invalid", valid=False),
            internal("hidden", hidden=True),
            internal("not-a-boolean", hard_stop="true"),
        )
    )["priority_briefing"]
    assert rows[0]["id"] == "stop" and rows[0]["triage_class"] == 0
    assert {row["id"] for row in rows} == {"stop", "overdue", "not-a-boolean"}
    assert all(row["hard_stop"] is False for row in rows[1:])


def test_due_date_then_older_age_then_id_with_offsets_and_missing_dates():
    rows = projection(
        alerts=(
            internal("missing", observed_at=NOW),
            internal("earliest", due_date="2026-08-29"),
            internal(
                "older-b", due_date="2026-08-30", created_at="2026-08-01T01:00:00+01:00"
            ),
            internal(
                "older-a",
                due_date="2026-08-30",
                created_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
            internal("newer", due_date="2026-08-30", created_at=NOW),
        )
    )["priority_briefing"]
    assert [row["id"] for row in rows] == [
        "earliest",
        "older-a",
        "older-b",
        "newer",
        "missing",
    ]


def test_tier_only_critical_precedes_high_without_fabricating_numeric_score():
    rows = projection(
        alerts=(
            internal("a-high", severity="HIGH"),
            internal("z-critical", severity="CRITICAL"),
        )
    )["priority_briefing"]
    assert [row["id"] for row in rows] == ["z-critical", "a-high"]
    assert all(
        row["underlying_score"] is None and row["score_kind"] == "TIER_ONLY"
        for row in rows
    )


def test_conservative_mappings_cover_every_current_enum():
    assert set(INTERNAL_NATURE) == {kind.value for kind in CommercialAlertKind}
    assert set(PUBLIC_NATURE) == {kind.value for kind in EventType}
    assert PUBLIC_NATURE["REGULATORY_CHANGE"] == "UNKNOWN"
    # A structured risk assessment overrides an otherwise positive/ambiguous type.
    row = projection(public("risk", event_type="PARTNERSHIP", risk={"score": 85}))[
        "priority_briefing"
    ][0]
    assert row["nature"] == "RISK"


def test_metadata_contract_is_optional_bounded_serializable_and_keeps_legacy_fields():
    assert PriorityMetadata().model_dump(exclude_unset=True) == {}
    assert PriorityMetadata().hard_stop is False
    with pytest.raises(ValidationError):
        PriorityMetadata(triage_class=4)
    with pytest.raises(ValidationError):
        PriorityMetadata(underlying_score=float("nan"))
    row = jsonable_encoder(
        projection(alerts=(internal("risk"),))["priority_briefing"][0]
    )
    metadata = PriorityMetadata.model_validate(
        {
            key: value
            for key, value in row.items()
            if key in PriorityMetadata.model_fields
        }
    )
    assert metadata.score_kind == "TIER_ONLY" and metadata.underlying_score is None
    assert row["id"] == "risk" and row["evidence_ids"] == ["internal-evidence"]
    assert row["reason"] == "Source reason" and row["recommended_action"] == "Review"
    assert row["high_importance"] is True
    assert "\u2014" not in row["triage_reason"]


def test_missing_fields_and_low_internal_confidence_are_honored():
    rows = projection(
        alerts=(
            internal("low-confidence", evidence_confidence={"score": 40}),
            internal("missing", missing_fields=("owner",)),
            internal("complete"),
        )
    )["priority_briefing"]
    assert [row["id"] for row in rows] == ["complete", "missing", "low-confidence"]
    assert rows[1]["assessment_complete"] is False
    assert rows[2]["triage_class"] == 2


def test_closed_duplicate_identity_suppresses_open_copy_regardless_of_input_order():
    alert = internal("same")
    item = {"id": alert.id, "kind": "COMMERCIAL_REVIEW", "alert_kind": alert.type}
    candidates = [
        priority_candidate(item, alert),
        priority_candidate(item, internal("same", status="DISMISSED")),
    ]
    assert (
        order_priorities(candidates)
        == order_priorities(list(reversed(candidates)))
        == ()
    )


def test_top_band_boundaries_do_not_use_confidence_as_opportunity_score():
    for score in (74.99, 75, 100):
        row = projection(public("opp", opportunity={"score": score}, confidence=100))[
            "priority_briefing"
        ][0]
        assert row["high_importance"] is (score >= 75)
    row = projection(public("no-score", confidence=100))["priority_briefing"][0]
    assert row["underlying_score"] is None and row["high_importance"] is False
    assert row["assessment_complete"] is False


def test_validation_lane_admission_and_placement_unchanged():
    validation = replace(
        public("validate", risk={"score": 100}),
        priority_eligible=False,
        commercial_relevance_state="REVIEW_REQUIRED",
    )
    result = projection(validation, alerts=(internal("internal"),))
    assert [row["id"] for row in result["priority_briefing"]] == ["internal"]
    assert [row["id"] for row in result["needs_validation_assessments"]] == ["validate"]
    assert "triage_class" not in result["needs_validation_assessments"][0]


def test_today_endpoint_keeps_existing_response_and_adds_validated_priority_metadata(
    monkeypatch,
):
    alert = CommercialAlert(
        id="api-risk",
        account_id="acct-1",
        type=CommercialAlertKind.BOOKINGS_DECLINE,
        business_unit=None,
        severity="HIGH",
        trigger_reason="Bookings declined",
        actual_value=0.3,
        threshold=0.25,
        evidence_ids=("internal-evidence",),
        observed_at=NOW,
        recommended_action="Review",
    )
    sample = SimpleNamespace(
        accounts=(), programs=(), commercial_contexts=(), quotes=(), orders=()
    )
    runtime = SimpleNamespace(
        environment=lambda: sample,
        observed_at=lambda: NOW,
        settings=SimpleNamespace(today_public_fixture_mode=False),
        monitor=SimpleNamespace(watch_targets={}, registry={}),
    )
    monkeypatch.setattr(today_api, "intelligence_signals", lambda runtime: [])
    monkeypatch.setattr(
        today_api, "monitor_health", lambda runtime: {"signal_briefs": ()}
    )
    monkeypatch.setattr(today_api, "federal_today_candidates", lambda runtime: [])
    monkeypatch.setattr(
        today_api.CommercialAlertEngine, "evaluate", lambda *args, **kwargs: (alert,)
    )
    app = FastAPI()
    app.include_router(today_api.router)
    app.dependency_overrides[today_api.get_runtime] = lambda: runtime
    with TestClient(app) as client:
        response = client.get("/today")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "data_mode",
        "priority_intelligence",
        "commercial_alerts",
        "recommended_actions",
        "command_center",
        "federal_opportunities",
    }
    row = body["command_center"]["priority_briefing"][0]
    contract = PriorityMetadata.model_validate(
        {
            key: value
            for key, value in row.items()
            if key in PriorityMetadata.model_fields
        }
    )
    assert contract.triage_class == 1 and contract.high_importance is True
    assert contract.alert_kind == "BOOKINGS_DECLINE" and contract.status == "OPEN"
    assert row["id"] == "api-risk" and row["kind"] == "COMMERCIAL_REVIEW"
    assert body["commercial_alerts"][0]["type"] == "BOOKINGS_DECLINE"
