from decimal import Decimal

import pytest

from btx_omni.modules.scoring.families import (
    FAMILIES,
    FactorInput,
    assess,
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
    assert result["data_coverage"]["ratio"] == Decimal(".2")
    assert len(result["data_coverage"]["missing_fields"]) == 4
    assert next(f for f in result["factors"] if f["key"] == "freshness")["points"] is None


def test_high_delivery_factors_cannot_overrule_constraint_or_missing_capacity():
    values = {k: 100 for k, _ in FAMILIES["delivery_feasibility"].weights}
    result = run("delivery_feasibility", values, blocking_constraints=("qualification-retracted",))
    assert result["score"] is None and result["status"] == "BLOCKED"
    del values["capacity"]
    assert run("delivery_feasibility", values)["score"] is None


def test_unknown_factor_and_untraced_points_rejected():
    with pytest.raises(ValueError, match="Unknown factor"):
        run("pwin", {"llm_probability": 99})
    with pytest.raises(ValueError, match="linked evidence"):
        FactorInput(Decimal(100), (), "Unsupported assertion")


def test_duplicate_articles_never_strengthen_public_risk():
    event = {"underlying_event_id": "closure", "active": True, "severity": 80, "risk_domain": "operations"}
    assert public_risk_rollup((event, event, event))["score"] == 80
    other = {**event, "underlying_event_id": "credit", "risk_domain": "finance"}
    assert public_risk_rollup((event, other))["score"] == 90
    assert public_risk_rollup(())["score"] is None


def test_opportunity_keeps_six_factors_and_pwin_is_not_probability():
    assert len(FAMILIES["opportunity_priority"].weights) == 6
    result = run("pwin", {k: 80 for k, _ in FAMILIES["pwin"].weights})
    assert result["score_unit"] == "POC_INDEX_0_TO_100"
    assert "not be displayed as a win probability" in result["interpretation"]


def test_coverage_counts_decision_fields_not_just_non_null_factor_scores():
    inputs = {key: FactorInput(Decimal(100), (key,), "Explicit partial evidence.", required_fields=("identity", "scope", "dated_record"), observed_fields=("identity",)) for key, _ in FAMILIES["delivery_feasibility"].weights}
    result = assess("delivery_feasibility", subject_id="solution", as_of="2026-08-31", revision="r1", inputs=inputs, eligible=True)
    assert result["data_coverage"]["factor_coverage"] == 1
    assert result["data_coverage"]["present"] == 4 and result["data_coverage"]["applicable"] == 12
    assert result["score"] is None


def test_partial_normalization_has_honest_effective_contributions():
    result = run("signal_confidence", {"source_reliability": 80, "entity_match": 80, "event_specificity": 80, "independent_corroboration": 80})
    assert result["score"] == 80
    assert abs(sum(f["contribution"] or 0 for f in result["factors"]) - result["score"]) <= Decimal(".02")


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
    assert first["decision_id"] != run("pwin", {**values, "solution_fit": 60})["decision_id"]
