import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from btx_omni.modules import federal_procurement
from btx_omni.modules.federal_procurement import (
    fixture,
    market_for,
    normalize_notice_type,
    procurement_projection,
    relevance,
)
from btx_omni.monitor.contracts import (
    RawEvidenceReference,
    SourceIdentity,
    SourceObservation,
    SourceVersion,
)


def test_official_sources_sought_normalization_is_conservative() -> None:
    assert normalize_notice_type("Sources Sought") == ("Sources Sought", True)
    assert normalize_notice_type("description mentions sources sought") == (
        "description mentions sources sought",
        False,
    )


def test_relevance_is_fit_first_and_deterministic() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    strong = {
        "naics": "336413",
        "naics_targeting": "VERIFIED",
        "notice_category": "Solicitation",
        "response_deadline": (now + timedelta(days=30)).isoformat(),
    }
    urgent_weak = {
        "notice_category": "Special Notice",
        "response_deadline": (now + timedelta(days=1)).isoformat(),
    }
    assert (
        relevance(strong, now=now)["score"] > relevance(urgent_weak, now=now)["score"]
    )
    assert relevance(strong, now=now) == relevance(strong, now=now)


def test_market_mapping_is_conservative() -> None:
    assert market_for("336413") == "Commercial Aerospace"
    assert market_for("999999") == "UNRESOLVED"


def test_fixture_has_typed_sam_and_award_fields() -> None:
    opportunities, awards = fixture(datetime(2026, 9, 1, tzinfo=UTC))
    assert opportunities[0]["sources_sought"] and opportunities[0]["set_aside"]
    assert opportunities[0]["evidence"]["collected_at"]
    assert awards[0]["fiscal_year"] == 2026 and awards[0]["fiscal_quarter"] == 2
    assert awards[0]["award_amount"] == "1200000"


def test_analytics_filters_and_aggregates_are_backend_owned() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    runtime = SimpleNamespace(
        observed_at=lambda: now,
        monitor=SimpleNamespace(observations={}),
        settings=SimpleNamespace(
            monitor_sam_naics_verification_state="PENDING_VERIFICATION",
            sam_api_key=None,
            federal_procurement_fixture_mode=True,
        ),
    )
    projection = procurement_projection(runtime, sources_sought=True)
    assert projection["active"]["kpis"]["sources_sought"] == 1
    assert len(projection["active"]["opportunities"]) == 1
    assert projection["active"]["pipeline"][2]["reason"] == "INSUFFICIENT_HISTORY"
    assert projection["awarded"]["available_fiscal_years"] == [2026, 2025]
    assert projection["awarded"]["top_recipients"][0]["recipient"] == "BTX Sample Prime"


def _runtime() -> SimpleNamespace:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    return SimpleNamespace(observed_at=lambda: now, monitor=SimpleNamespace(observations={}), settings=SimpleNamespace(monitor_sam_naics_verification_state="PENDING_VERIFICATION", sam_api_key=None, federal_procurement_fixture_mode=True))


def test_sources_sought_filter() -> None:
    assert len(procurement_projection(_runtime(), sources_sought=True)["active"]["opportunities"]) == 1


def test_naics_filter() -> None:
    assert procurement_projection(_runtime(), naics="334413")["active"]["opportunities"][0]["market"] == "Semiconductor"


def test_notice_and_set_aside_filters() -> None:
    projection = procurement_projection(_runtime(), notice_type="Solicitation", set_aside="Total Small Business")
    assert [x["opportunity_id"] for x in projection["active"]["opportunities"]] == ["SAM-2"]


def test_deadline_and_sector_filters() -> None:
    projection = procurement_projection(_runtime(), deadline_bucket="14_DAYS", sector="Semiconductor")
    assert [x["opportunity_id"] for x in projection["active"]["opportunities"]] == ["SAM-2"]


def test_projection_tolerates_live_sam_notice_without_response_deadline(
    monkeypatch,
) -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    runtime = SimpleNamespace(
        observed_at=lambda: now,
        monitor=SimpleNamespace(observations={}),
        settings=SimpleNamespace(
            monitor_sam_naics_verification_state="PENDING_VERIFICATION",
            sam_api_key="configured",
            federal_procurement_fixture_mode=True,
        ),
    )
    monkeypatch.setattr(
        federal_procurement,
        "fixture",
        lambda _now: (
            [
                {
                    "opportunity_id": "live-no-deadline",
                    "notice_category": "Solicitation",
                    "sources_sought": False,
                    "naics": None,
                    "set_aside": None,
                    "market": "UNRESOLVED",
                    "response_deadline": None,
                    "posted_date": now.isoformat(),
                }
            ],
            [],
        ),
    )
    projection = procurement_projection(runtime)
    # A live SAM item without a response deadline is still a valid record;
    # it must not make the federal-procurement reporting path crash.
    assert projection["active"]["kpis"]["closing_within_14_days"] == 0


def test_relevance_missing_context_is_conservative() -> None:
    score = relevance({"naics": "336413", "naics_targeting": "VERIFIED"}, now=datetime(2026, 9, 1, tzinfo=UTC))
    assert score["score"] == 40
    assert "Relevant BTX commercial context" in score["missingness"]


def test_sector_totals_and_scope_are_truthful() -> None:
    awarded = procurement_projection(_runtime())["awarded"]
    assert awarded["kpis"]["total_award_amount"] == "1700000"
    assert {x["sector"] for x in awarded["sector_totals"]} == {"Commercial Aerospace", "Semiconductor"}


def test_fiscal_year_filter_changes_total() -> None:
    projection = procurement_projection(_runtime(), fiscal_year=2025)
    assert projection["awarded"]["kpis"]["total_award_amount"] == "800000"


def test_delta_and_lag_are_explicitly_unavailable() -> None:
    projection = procurement_projection(_runtime())
    assert all(row["delta"] is None for row in projection["active"]["pipeline"])
    assert projection["awarded"]["lag"]["state"] == "INSUFFICIENT_HISTORY"


def test_connected_awards_stay_inside_verified_naics_scope() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)

    def observation(identifier: str, naics: str) -> SourceObservation:
        identity = SourceIdentity("usaspending", identifier)
        version = SourceVersion(identifier, "1", identifier, now, now)
        evidence = RawEvidenceReference(
            f"e-{identifier}",
            identity,
            version,
            f"https://api.usaspending.gov/{identifier}",
            now,
            identifier,
            "application/json",
        )
        return SourceObservation(
            identifier,
            identity,
            version,
            now,
            identifier,
            evidence,
            now,
            evidence.locator,
            "TIER_1_AUTHORITATIVE_STRUCTURED",
            "run",
            json.dumps(
                {
                    "Action Date": now.isoformat(),
                    "Transaction Amount": "100",
                    "NAICS": naics,
                    "Recipient Name": "Boeing",
                }
            ),
        )

    runtime = SimpleNamespace(
        observed_at=lambda: now,
        monitor=SimpleNamespace(
            observations={
                item.id: item
                for item in (
                    observation("in", "336413"),
                    observation("out", "541990"),
                )
            }
        ),
        settings=SimpleNamespace(
            monitor_sam_naics_verification_state="VERIFIED",
            monitor_sam_naics="336413",
            sam_api_key="configured",
            federal_procurement_fixture_mode=False,
        ),
    )
    projection = procurement_projection(runtime)
    assert [
        item["canonical_source_id"] for item in projection["awarded"]["awards"]
    ] == ["in"]
    assert projection["usaspending"]["scope"] == "VERIFIED_NAICS_SCOPE"
