from decimal import Decimal
from types import SimpleNamespace

import pytest

from btx_omni.modules.scoring.families import (
    FAMILIES,
    FactorInput,
    assess,
    customer_risk_projection,
    overall_customer_risk,
    public_risk_rollup,
)


def run(family, values, **kwargs):
    return assess(family, subject_id="subject", as_of="2026-08-31", revision="r1", inputs={k: FactorInput(Decimal(v), (f"e:{k}",), "Evidence-specific test factor.") for k, v in values.items()}, eligible=True, **kwargs)


def test_confidence_uses_agreed_weights_and_never_modifies_risk():
    confidence = run("signal_confidence", {"source_reliability": 100, "entity_match": 80, "event_specificity": 50, "independent_corroboration": 0, "freshness": 100})
    assert confidence["score"] == 70
    risk = run("risk_severity", {k: 90 for k, _ in FAMILIES["risk_severity"].weights})
    assert risk["score"] == 90
    assert "signal_confidence" not in {r["key"] for r in risk["factors"]}


def test_missing_fields_do_not_disappear_or_become_zero():
    result = run("signal_confidence", {"source_reliability": 100})
    assert result["score"] is None
    assert result["data_coverage"]["ratio"] == Decimal(".30")
    assert result["score_range"] == {"low": 30, "high": 100}
    assert len(result["data_coverage"]["missing_fields"]) == 4
    assert next(f for f in result["factors"] if f["key"] == "freshness")["points"] is None


def test_high_delivery_factors_cannot_overrule_constraint_or_missing_capacity():
    values = {k: 100 for k, _ in FAMILIES["delivery_feasibility"].weights}
    result = run("delivery_feasibility", values, blocking_constraints=("qualification-retracted",))
    assert result["score"] is None and result["status"] == "BLOCKED"
    del values["schedule_feasibility"]
    assert run("delivery_feasibility", values)["score"] is None


def test_unknown_factor_and_untraced_points_rejected():
    with pytest.raises(ValueError, match="Unknown factor"):
        run("pwin", {"llm_probability": 99})
    with pytest.raises(ValueError, match="linked evidence"):
        FactorInput(Decimal(100), (), "Unsupported assertion")


def test_duplicate_articles_never_strengthen_public_risk():
    event = {"underlying_event_id": "closure", "active": True, "severity": 80, "signal_confidence": 70, "risk_domain": "operations/site"}
    assert public_risk_rollup((event, event, event))["score"] == 80
    other = {**event, "underlying_event_id": "credit", "risk_domain": "financial/legal"}
    assert public_risk_rollup((event, other))["score"] == 85
    assert public_risk_rollup(())["score"] is None
    assert public_risk_rollup((), monitoring_complete=True)["score"] == 0
    assert public_risk_rollup((event, {**other, "signal_confidence": 69}))["score"] == 80
    third = {**event, "underlying_event_id": "demand", "risk_domain": "demand/program"}
    assert public_risk_rollup((event, other, third))["score"] == 90


def test_customer_risk_projection_keeps_public_internal_and_missingness_separate():
    current = SimpleNamespace(
        id="risk-1", canonical_account_ids=("boeing",), freshness="CURRENT",
        seller_promotion_state="RESOLVED_ELIGIBLE", event_type="PRODUCTION_DELAY",
        risk_severity={"score": 80}, signal_confidence={"status": "SCORED", "score": 70},
    )
    copied = SimpleNamespace(**{**current.__dict__, "id": "risk-2", "canonical_account_ids": ("kla",)})
    result = customer_risk_projection(
        account_id="boeing", current_customer=True,
        internal_decision={"score": 60}, signal_briefs=(copied, current),
    )
    assert result["public_risk_rollup"]["score"] == 80
    assert result["public_risk_rollup"]["independent_event_ids"] == ("risk-1",)
    assert result["overall_customer_risk"]["score"] == 68
    assert result["confirmed_public_event_ids"] == ("risk-1",)

    missing = customer_risk_projection(
        account_id="boeing", current_customer=True,
        internal_decision={"score": 60}, signal_briefs=(),
    )
    assert missing["overall_customer_risk"]["score"] is None
    assert missing["overall_customer_risk"]["missing_fields"] == ("public_risk_rollup",)


def test_opportunity_keeps_six_factors_and_pwin_is_not_probability():
    assert len(FAMILIES["opportunity_priority"].weights) == 6
    result = run("pwin", {k: 80 for k, _ in FAMILIES["pwin"].weights})
    assert result["score_unit"] == "POC_INDEX_0_TO_100"
    assert "not a calibrated win probability" in result["interpretation"]


def test_coverage_counts_decision_fields_not_just_non_null_factor_scores():
    inputs = {key: FactorInput(Decimal(100), (key,), "Explicit partial evidence.", required_fields=("identity", "scope", "dated_record"), observed_fields=("identity",)) for key, _ in FAMILIES["delivery_feasibility"].weights}
    result = assess("delivery_feasibility", subject_id="solution", as_of="2026-08-31", revision="r1", inputs=inputs, eligible=True)
    assert result["data_coverage"]["factor_coverage"] == 1
    assert result["data_coverage"]["present"] == 6 and result["data_coverage"]["applicable"] == 18
    assert result["score"] is None


def test_partial_evidence_retains_fixed_weights_and_a_range():
    result = run("signal_confidence", {"source_reliability": 80, "entity_match": 80, "event_specificity": 80, "independent_corroboration": 80})
    assert result["score"] is None
    assert result["score_range"] == {"low": 72, "high": 82}
    assert sum(f["contribution"] or 0 for f in result["factors"]) == 72
    assert [f["effective_weight_percent"] for f in result["factors"]] == [30, 25, 20, 15, 10]


def test_known_zero_and_unknown_have_different_ranges_and_coverage():
    values = {k: 0 for k, _ in FAMILIES["signal_confidence"].weights}
    complete = run("signal_confidence", values)
    assert complete["score"] == 0
    assert complete["score_range"] == {"low": 0, "high": 0}
    del values["freshness"]
    partial = run("signal_confidence", values)
    assert partial["score"] is None
    assert partial["score_range"] == {"low": 0, "high": 10}


def test_nested_partial_factor_preserves_known_leaf_contributions_without_reweighting():
    result = assess("opportunity_priority", subject_id="pursuit", as_of="2026-08-31", revision="r2", eligible=True,
        inputs={"program_durability": FactorInput(None, ("horizon-source",), "Known horizon, other conditions unresolved.", lower_bound=Decimal(40), upper_bound=Decimal(100))})
    assert result["score"] is None
    assert result["score_range"] == {"low": 12, "high": 100}
    assert result["data_coverage"]["ratio"] == 0
    with pytest.raises(ValueError, match="Invalid partial"):
        FactorInput(None, ("source",), "Invalid bounds.", lower_bound=Decimal(90), upper_bound=Decimal(10))


def test_overall_risk_requires_customer_and_both_sources_then_applies_agreed_floors():
    args = {"current_customer": True, "internal_score": Decimal(10), "public_score": Decimal(90), "public_confirmed": True}
    assert overall_customer_risk(**args)["score"] == 75
    assert overall_customer_risk(**{**args, "internal_score": Decimal(90), "public_score": Decimal(10)})["score"] == 80
    assert overall_customer_risk(**args, critical_override_evidence_ids=("critical-record",))["score"] == 85
    missing = overall_customer_risk(**{**args, "internal_score": None})
    assert missing["score"] is None and missing["applicable_floors"]
    prospect = overall_customer_risk(**{**args, "current_customer": False})
    assert prospect["score"] is None and prospect["status"] == "INELIGIBLE"


def test_convergence_needs_causal_evidence_not_just_two_high_numbers():
    args = {"current_customer": True, "internal_score": Decimal(60), "public_score": Decimal(70), "public_confirmed": True}
    assert overall_customer_risk(**args)["score"] == 64
    assert overall_customer_risk(**args, convergence_evidence_ids=("linked-causal-assessment",))["score"] == 69


def test_decision_reference_is_stable_but_changes_when_supported_input_changes():
    values = {k: 80 for k, _ in FAMILIES["pwin"].weights}
    first = run("pwin", values)
    assert first["decision_id"] == run("pwin", dict(reversed(list(values.items()))))["decision_id"]
    assert first["decision_id"] != run("pwin", {**values, "requirement_fit": 60})["decision_id"]
