from datetime import UTC, datetime

from btx_omni.ai.config import AiConfig
from btx_omni.core.config import Settings
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.domain.work import PrincipalRole
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.federal_opportunity_routing import build_assessment
from btx_omni.modules.federal_procurement import fixture
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_curated_public_scenarios_preserve_source_truth_without_claiming_btx_participation() -> None:
    environment = build_sample_environment()
    accounts = {account.id: account for account in environment.accounts}
    scenarios = environment.rich_scenarios

    assert accounts["boeing"].relationship is AccountRelationship.CURRENT_CUSTOMER
    assert accounts["lockheed-martin"].relationship is AccountRelationship.CURRENT_CUSTOMER
    assert accounts["huxwrx"].relationship is AccountRelationship.CURRENT_CUSTOMER

    boeing = scenarios["boeing"]
    assert boeing.event.source_url.startswith("https://www.faa.gov/")
    assert boeing.event.occurred_at.date().isoformat() == "2025-03-14"
    assert "review" in boeing.recommended_next_step.casefold()

    lockheed = scenarios["lockheed-martin"]
    assert lockheed.event.source_url.startswith("https://www.nasa.gov/")
    assert "coordinate" in lockheed.recommended_next_step.casefold()
    assert "participat" not in (
        lockheed.reason_for_attention + lockheed.recommended_next_step
    ).casefold()

    assert all(
        scenario.event.source_url.startswith("https://")
        and scenario.event.occurred_at.tzinfo is not None
        for scenario in scenarios.values()
    )


def test_sample_federal_routes_are_replay_stable_but_do_not_qualify_live_or_durable_claims() -> None:
    environment = build_sample_environment()
    opportunities, awards = fixture(NOW)
    opportunity = opportunities[0]

    baseline = build_assessment(
        opportunity,
        environment=environment,
        awards=awards,
        partnerships=set(),
        now=NOW,
    )
    replay = build_assessment(
        opportunity,
        environment=environment,
        awards=awards,
        partnerships=set(),
        now=NOW,
    )

    assert opportunity["data_mode"] == "SAMPLE"
    assert opportunity["official_source_url"].endswith("/SAM-1")
    assert baseline["input_revision"] == replay["input_revision"]
    assert baseline["durability"]["state"] == "ONE_TIME_OR_UNKNOWN"
    assert baseline["durability"]["historical_award_count"] == 0
    assert "STRATEGIC_PARTNER" not in {
        route["route_type"] for route in baseline["routes"]
    }
    assert "not an open bid" in baseline["stage"]["explanation"]

    designated = build_assessment(
        opportunity,
        environment=environment,
        awards=awards,
        partnerships={"ge-aerospace"},
        now=NOW,
    )
    partner_route = next(
        route
        for route in designated["routes"]
        if route["route_type"] == "STRATEGIC_PARTNER"
    )
    assert partner_route["evidence_state"] == "SUPPORTED_CONTEXT_REQUIRES_VALIDATION"
    assert "authority" in " ".join(partner_route["unknowns"]).casefold()
    assert "validate" in partner_route["governed_action"].casefold()


def test_internal_customer_risk_has_canonical_evidence_and_a_governed_action() -> None:
    environment = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(
        environment.commercial_contexts,
        environment.quotes,
        orders=environment.orders,
        observed_at=NOW,
    )
    overdue = next(
        alert
        for alert in alerts
        if alert.account_id == "lockheed-martin"
        and alert.trigger_reason == "Order is past its promised ship date"
    )

    assert overdue.severity == "HIGH"
    assert overdue.evidence_ids
    assert overdue.recommended_action == "Confirm fulfillment status and customer recovery plan."


def test_provider_and_role_readiness_stays_inside_existing_authority_model() -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key=None,
        google_cloud_project=None,
        sam_api_key=None,
        monitor_mode="disabled",
        monitor_durable_state_enabled=False,
        monitor_schedule_configured=False,
    )
    ai = AiConfig.from_settings(settings)

    assert ai.api_key is None and ai.project is None
    assert settings.sam_api_key is None
    assert settings.monitor_mode == "disabled"
    assert settings.monitor_durable_state_enabled is False
    assert settings.monitor_schedule_configured is False
    assert set(PrincipalRole) == {
        PrincipalRole.SALESPERSON,
        PrincipalRole.MANAGER,
    }
