"""Count distinct component families in the accepted scoped quote revision."""

from btx_omni.modules.classification import SAMPLE_CLASSIFIER_RULE_VERSION
from btx_omni.modules.classification.contract import deterministic_bin

PATH = "addressable_btx_work.btx_relevant_component_content"


def classify_component_content(account: dict, opportunity: dict, component_classes: tuple, *, as_of: str):
    revision = next((row for row in account["quote_revisions"]
                     if row["quote_revision_id"] == opportunity.get("quote_revision_id")), None)
    lines = [row for row in account["quote_lines"] if revision and
             row["quote_line_id"] in revision["line_ids"]]
    known = {item.id for item in component_classes}
    families = {row["component_id"] for row in lines if row["component_id"] in known}
    scoped = opportunity.get("component_id") in families
    complete = bool(revision and lines and len(lines) == len(revision["line_ids"]) and scoped and
                    len(families) == len({row["component_id"] for row in lines}))
    return deterministic_bin(
        opportunity_id=opportunity["opportunity_id"], path=PATH,
        bin_value="MULTIPLE_FAMILIES" if complete and len(families) >= 2 else "ONE_FAMILY" if complete else None,
        evidence_ids=tuple(sorted((revision["quote_revision_id"], *(row["quote_line_id"] for row in lines), *families))) if complete else (),
        missing_fields=() if complete else ("scoped_quote_revision.component_class_ids",),
        as_of=as_of, rule_version=SAMPLE_CLASSIFIER_RULE_VERSION,
    )
