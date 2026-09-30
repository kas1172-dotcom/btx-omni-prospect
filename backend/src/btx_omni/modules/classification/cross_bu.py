"""Count declared canonical BU mappings for one scoped component."""

from btx_omni.modules.classification import SAMPLE_CLASSIFIER_RULE_VERSION
from btx_omni.modules.classification.contract import deterministic_bin

PATH = "addressable_btx_work.cross_bu_applicability"


def classify_cross_bu(opportunity: dict, component_classes: tuple, *, as_of: str):
    component = next((item for item in component_classes if item.id == opportunity.get("component_id")), None)
    units = set(component.business_unit_ids) if component else set()
    return deterministic_bin(
        opportunity_id=opportunity["opportunity_id"], path=PATH,
        bin_value="TWO_PLUS_BU" if len(units) >= 2 else "ONE_BU" if len(units) == 1 else None,
        evidence_ids=(component.id,) if units else (),
        missing_fields=() if units else ("component_class.business_unit_ids",),
        as_of=as_of, rule_version=SAMPLE_CLASSIFIER_RULE_VERSION,
    )
