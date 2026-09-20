"""Rubric v2.0 corrected examples; exact contributions, not model predictions.

No fixture files, application startup, database or network access is needed.
The same single-primary-source inputs yield 86.25 at nine days, not 85.75.
The amended user specification resolves the original nine-day target to 86.25.
"""
from decimal import Decimal

import pytest

from btx_omni.modules.scoring.families import (
    FAMILIES,
    FactorInput,
    assess,
    overall_customer_risk,
)
from btx_omni.modules.scoring.public_rules import freshness_points
from btx_omni.modules.scoring.pursuit_inputs import factor_points


def confidence(age_days):
    points = {
        "source_reliability": 100, "entity_match": 100,
        "event_specificity": 100, "independent_corroboration": 25,
        "freshness": freshness_points(age_days * 24, 30 * 24),
    }
    return assess(
        "signal_confidence", subject_id="fictional-preflight-only",
        as_of="2026-09-20", revision="preflight", eligible=True,
        inputs={key: FactorInput(Decimal(value), ("fictional-test-evidence",),
                                "Arithmetic probe, not a public assertion.")
                for key, value in points.items()},
    )


@pytest.mark.parametrize(("days", "freshness"), [(3, "10"), (9, "7.5"), (27, "5"), (31, "0")])
def test_confidence_freshness_quarters(days, freshness):
    factor = next(f for f in confidence(days)["factors"] if f["key"] == "freshness")
    assert factor["contribution"] == Decimal(freshness)


def test_three_day_confidence_target():
    assert confidence(3)["score"] == Decimal("88.75")


def test_requested_nine_day_confidence_target():
    """Amended section 4: 30 + 25 + 20 + 3.75 + 7.5 = 86.25."""
    assert confidence(9)["score"] == Decimal("86.25")


def test_customer_rollup_erratum():
    result = overall_customer_risk(
        current_customer=True, internal_score=Decimal("52.5"),
        public_score=Decimal("76.25"), public_confirmed=True,
    )
    assert result["score"] == Decimal("62.00")
    assert result["convergence_uplift"] == 0
    assert result["applicable_floors"] == []


def test_delivery_erratum_from_raw_bins():
    raw = {
        "capability_match": {"state": "ONE_FUNDED_DATED_NONCRITICAL_GAP"},
        "schedule_feasibility": {"net_available_hours": 110, "required_hours": 100},
        "material_readiness": {"most_constrained_critical_material_days_early": 14},
        "quality_certification": {"state": "VALID_BUYER_QUALIFICATION_SCHEDULED"},
        "margin": {"quoted_minor": 100, "estimated_total_cost_minor": 90},
        "coordination": {"state": "ONE_DATE_UNKNOWN"},
    }
    result = assess(
        "delivery_feasibility", subject_id="fictional-preflight-only",
        as_of="2026-09-20", revision="preflight", eligible=True,
        inputs={key: FactorInput(factor_points(key, value), ("fictional-test-evidence",),
                                "Raw band observation; not a qualified real pursuit.")
                for key, value in raw.items()},
    )
    assert [f["contribution"] for f in result["factors"]] == [
        Decimal(v) for v in ("22.5", "18.75", "11.25", "11.25", "5", "3.75")
    ]
    assert result["score"] == Decimal("72.50")


def test_public_risk_factor_name():
    assert "mitigation" in dict(FAMILIES["risk_severity"].weights)
