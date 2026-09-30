"""Boeing Path A proof uses existing SAMPLE raw records and preserves bins."""

from copy import deepcopy

from btx_omni.modules.classification.commercial_adjacency import classify_commercial_adjacency
from btx_omni.modules.classification.component_content import classify_component_content
from btx_omni.modules.classification.cross_bu import classify_cross_bu
from btx_omni.modules.classification.program_horizon import classify_program_horizon
from btx_omni.modules.scoring.account_attractiveness import ADJACENCY, CONTENT, CROSS_BU, FACTORS, HORIZON
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment


def boeing_case():
    environment = enhance_environment(build_sample_environment())
    account = environment.commercial_ledgers["boeing"]
    opportunity = next(row for row in account["opportunities"]
                       if row["opportunity_id"] == "demo:j7:boeing:recovery-expansion")
    return environment, account, opportunity


EXPECTED_PATH_A_FACTOR_COUNT = 8


def test_boeing_classifications_are_unique_and_three_original_bins_remain_legal():
    environment, account, opportunity = boeing_case()
    results = (
        (classify_commercial_adjacency(account, opportunity, as_of=account["as_of"]), ADJACENCY),
        (classify_cross_bu(opportunity, environment.component_classes, as_of=account["as_of"]), CROSS_BU),
        (classify_component_content(account, opportunity, environment.component_classes, as_of=account["as_of"]), CONTENT),
        (classify_program_horizon(opportunity, next(p for p in environment.programs
                                                   if p.id == opportunity["program_id"]), as_of=account["as_of"]), HORIZON),
    )
    rows = opportunity["score_observations"]
    observations = {row["path"]: row for row in rows}
    expected_paths = {
        factor.key + "." + leaf.rubric.key
        for factor in FACTORS for leaf in factor.subfactors
    } | {factor.key for factor in FACTORS if factor.single_rubric is not None}
    assert len(expected_paths) == 18
    assert len(rows) == len(observations) == len(expected_paths)
    assert set(observations) == expected_paths
    for path, row in observations.items():
        classification = row["classification"]
        assert classification["factor_path"] == path
        assert classification["method"] in {"DETERMINISTIC", "SYNTHETIC_AUTHORED"}
    assert sum(row["classification"]["method"] == "DETERMINISTIC" for row in rows) == EXPECTED_PATH_A_FACTOR_COUNT
    for classification, rubric in results:
        assert classification.method == "DETERMINISTIC"
        assert classification.classifier_rule_version and classification.evidence_ids
        assert rubric.bin_for(classification.bin_value)
        assert observations[classification.factor_path]["bin"] == classification.bin_value
        assert observations[classification.factor_path]["classification"]["method"] == "DETERMINISTIC"
    assert all(row["classification"]["provenance"]["truth_class"] == "POC_SCENARIO" for row in observations.values())
    decision = customer_decisions(account, account_id="boeing", revision=environment.commercial_revision,
                                  current_customer=True, facility_ids=frozenset(f.id for f in environment.btx_facilities))
    pursuit = next(row for row in decision["opportunities"] if row["opportunity_id"] == opportunity["opportunity_id"])
    assert pursuit["opportunity_priority"]["score"] is not None


def test_missing_inputs_do_not_become_default_bins():
    environment, account, opportunity = boeing_case()
    missing_history = deepcopy(account)
    missing_history["monthly_commercial_history"] = []
    missing_lines = deepcopy(account)
    missing_lines["quote_lines"] = []
    cases = (
        classify_commercial_adjacency(missing_history, opportunity, as_of=account["as_of"]),
        classify_cross_bu(opportunity, (), as_of=account["as_of"]),
        classify_component_content(missing_lines, opportunity, environment.component_classes, as_of=account["as_of"]),
    )
    for classification in cases:
        assert classification.state == "MISSING"
        assert classification.bin_value is None
        assert classification.provenance.missing_fields


def test_program_horizon_uses_canonical_program_and_v2_rule():
    from dataclasses import replace

    from btx_omni.modules.classification import FACILITY_CLASSIFIER_RULE_VERSION

    environment, account, opportunity = boeing_case()
    program = next(p for p in environment.programs if p.id == opportunity["program_id"])
    assert program.expected_production_horizon_years == 3
    result = classify_program_horizon(opportunity, program, as_of=account["as_of"])
    assert (result.bin_value, result.state, result.method) == (
        "TWO_TO_FOUR_YEARS", "CURRENT", "DETERMINISTIC")
    assert result.classifier_rule_version == FACILITY_CLASSIFIER_RULE_VERSION
    assert result.evidence_ids == (program.id,)
    assert HORIZON.bin_for(result.bin_value)
    missing = classify_program_horizon(opportunity,
        replace(program, expected_production_horizon_years=None), as_of=account["as_of"])
    assert missing.state == "MISSING" and missing.bin_value is None
    assert missing.provenance.missing_fields == ("program.expected_production_horizon_years",)
