from btx_omni.modules.accounts.customer_360 import organization_360_projection
from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.monitor.business_briefings import _selected_records
from btx_omni.providers.sample.environment import build_sample_environment


def test_organization_mode_is_owned_by_canonical_relationship_and_history() -> None:
    environment = build_sample_environment()
    read = CommercialReadService(environment)
    customer = next(item for item in environment.accounts if item.id == "lockheed-martin")
    prospect = next(item for item in environment.accounts if item.id == "intel")
    contradictory = next(
        item for item in environment.accounts if item.id == "rtx-collins-aerospace"
    )

    customer_view = organization_360_projection(
        account=customer,
        commercial=read.account_snapshot(customer.id),
        signals=[],
    )
    prospect_view = organization_360_projection(
        account=prospect,
        commercial=read.account_snapshot(prospect.id),
        signals=[],
    )
    review_view = organization_360_projection(
        account=contradictory,
        commercial=read.account_snapshot(contradictory.id),
        signals=[],
    )

    assert customer_view["mode"] == "CUSTOMER"
    assert prospect_view["mode"] == "PROSPECT"
    assert prospect_view["has_commercial_history"] is False
    assert review_view["mode"] == "RELATIONSHIP_REVIEW"


def test_customer_expansion_reuses_current_assessment_identity() -> None:
    environment = build_sample_environment()
    read = CommercialReadService(environment)
    account = next(item for item in environment.accounts if item.id == "lockheed-martin")
    assessment = {
        "id": "event-javelin",
        "assessment_id": "assessment-javelin",
        "assessment_version": 4,
        "analysis_status": "READY",
        "commercial_relevance_state": "REVIEW_REQUIRED",
        "canonical_program_id": "program-javelin",
        "headline": "Javelin production announcement",
        "recommended_action": "Validate internal Lockheed and RTX records.",
        "technical_opportunity": {"components": [{"name": "Round"}]},
    }
    result = organization_360_projection(
        account=account,
        commercial=read.account_snapshot(account.id),
        signals=[{"business_briefing": assessment}],
    )

    assert result["mode"] == "CUSTOMER"
    assert result["expansion_pursuit"] == {
        "assessment_id": "assessment-javelin",
        "assessment_version": 4,
        "event_id": "event-javelin",
        "headline": "Javelin production announcement",
        "program_id": "program-javelin",
        "governed_action": "Validate internal Lockheed and RTX records.",
    }


def test_related_activity_has_plain_language_match_reasons_without_changing_scope() -> None:
    ledger = {
        "programs": [{"program_id": "p-1", "name": "Program One"}],
        "components": [{"component_id": "c-1", "name": "Housing"}],
        "order_lines": [
            {
                "order_line_id": "line-1",
                "order_id": "order-1",
                "program_id": "p-1",
                "component_id": "c-1",
                "business_unit_id": "bu-1",
                "line_total_minor": 1000,
            }
        ],
        "orders": [{"order_id": "order-1", "quote_id": "quote-1"}],
        "quotes": [{"quote_id": "quote-1", "rfq_id": "rfq-1"}],
        "rfqs": [{"rfq_id": "rfq-1"}],
    }

    records, scope = _selected_records(ledger, "p-1", {"c-1"})

    assert scope == "EXACT_PROGRAM"
    line = next(item for item in records if item["record_id"] == "line-1")
    assert line["display_name"] == "Housing"
    assert line["match_strength"] == "Strong scoped match"
    assert "Shares the same recorded program scope" in line["match_reasons"]
    assert "remain unconfirmed" in line["unknowns"]
