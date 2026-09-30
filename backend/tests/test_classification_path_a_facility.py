"""Boeing facility Path A uses declared SAMPLE scope and retained site capabilities."""

from copy import deepcopy

from btx_omni.domain.common import DataMode
from btx_omni.modules.classification.facility_fit import (
    classify_certification_compliance_fit, classify_delivery_capability_match,
    classify_delivery_quality_certification, classify_delivery_schedule_feasibility,
    classify_material_match, classify_process_tolerance_match, classify_volume_compatibility,
)
from btx_omni.modules.scoring.account_attractiveness import CERT, MATERIAL, PROCESS, VOLUME
from btx_omni.modules.scoring.pursuit_inputs import factor_points
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment


BIN_RULES = (
    (classify_material_match, MATERIAL),
    (classify_process_tolerance_match, PROCESS),
    (classify_certification_compliance_fit, CERT),
    (classify_volume_compatibility, VOLUME),
)
DELIVERY_RULES = (
    classify_delivery_capability_match,
    classify_delivery_schedule_feasibility,
    classify_delivery_quality_certification,
)


def boeing_case():
    environment = enhance_environment(build_sample_environment())
    account = environment.commercial_ledgers["boeing"]
    opportunity = next(row for row in account["opportunities"]
                       if row["opportunity_id"] == "demo:j7:boeing:recovery-expansion")
    facility = next(row for row in environment.btx_facilities
                    if row.id == opportunity["delivery_facility_id"])
    return account, opportunity, facility


def test_facility_rules_are_deterministic_legal_and_wired():
    account, opportunity, facility = boeing_case()
    scope = opportunity["scope_requirements"]
    assert (scope["data_mode"], scope["synthetic"], scope["source"]) == (
        "SAMPLE", True, "Authored SAMPLE scope requirements")
    observations = {row["path"]: row for row in opportunity["score_observations"]}
    for classify, rubric in BIN_RULES:
        result = classify(opportunity, facility, as_of=account["as_of"])
        assert result.method == "DETERMINISTIC" and result.state == "CURRENT"
        assert result.classifier_rule_version and result.evidence_ids
        assert result.provenance.data_mode == DataMode.SAMPLE and result.provenance.synthetic
        assert "SAMPLE" in result.note
        assert rubric.bin_for(result.bin_value)
        assert observations[result.factor_path]["bin"] == result.bin_value
        assert observations[result.factor_path]["classification"]["method"] == "DETERMINISTIC"
    assert {classify(opportunity, facility, as_of=account["as_of"]).bin_value for classify, _ in BIN_RULES} == {
        "ROUTINE", "MINOR_GAP", "NORMAL_RANGE"}
    for classify in DELIVERY_RULES:
        result = classify(opportunity, facility, as_of=account["as_of"])
        assert result.method == "DETERMINISTIC" and result.state == "CURRENT"
        assert result.classifier_rule_version and result.evidence_ids
        assert result.provenance.data_mode == DataMode.SAMPLE and result.provenance.synthetic
        assert "SAMPLE" in result.note
        row = opportunity["scoring_inputs"]["delivery_feasibility"][result.factor_path]
        assert row["classification"]["method"] == "DETERMINISTIC"
        assert factor_points(result.factor_path, dict(result.raw_input)) is not None
        if result.factor_path == "schedule_feasibility":
            assert set(result.raw_input) == {"net_available_hours", "required_hours"}
            assert dict(result.raw_input) == {"net_available_hours": 2080, "required_hours": 270}
        else:
            assert set(result.raw_input) == {"state"}


def test_all_facility_rules_report_missing_scope_or_facility():
    account, opportunity, facility = boeing_case()
    without_scope = deepcopy(opportunity)
    without_scope.pop("scope_requirements")
    for classify in (*[rule for rule, _ in BIN_RULES], *DELIVERY_RULES):
        result = classify(without_scope, facility, as_of=account["as_of"])
        assert result.state == "MISSING" and result.bin_value is None and result.raw_input is None
        assert any(field.startswith("scope_requirements.") for field in result.provenance.missing_fields)
        result = classify(opportunity, None, as_of=account["as_of"])
        assert result.state == "MISSING" and result.bin_value is None and result.raw_input is None
        assert "delivery_facility_id" in result.provenance.missing_fields
