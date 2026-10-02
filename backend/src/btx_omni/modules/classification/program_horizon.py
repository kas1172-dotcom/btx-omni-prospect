"""Derive a pursuit horizon bin from its canonical SAMPLE Program."""

from dataclasses import replace

from btx_omni.modules.classification import FACILITY_CLASSIFIER_RULE_VERSION
from btx_omni.modules.classification.contract import deterministic_bin

PATH = "program_durability.expected_production_horizon"


def classify_program_horizon(opportunity: dict, program: object | None, *, as_of: str):
    years = getattr(program, "expected_production_horizon_years", None)
    valid = (program is not None and program.id == opportunity.get("program_id")
             and type(years) is int and years >= 0)
    value = None
    if valid:
        value = ("TEN_PLUS_YEARS" if years >= 10 else "FIVE_TO_NINE_YEARS" if years >= 5
                 else "TWO_TO_FOUR_YEARS" if years >= 2 else "UNDER_TWO_YEARS_OR_ONE_OFF")
    result = deterministic_bin(
        opportunity_id=opportunity["opportunity_id"], path=PATH, bin_value=value,
        evidence_ids=(program.id,) if valid else (),
        missing_fields=() if valid else ("program.expected_production_horizon_years",),
        as_of=as_of, rule_version=FACILITY_CLASSIFIER_RULE_VERSION,
    )
    return replace(result, note="Derived from an authored SAMPLE program horizon, not a verified Boeing production plan.")
