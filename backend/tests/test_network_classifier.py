import pytest

from btx_omni.modules.relationships.network_classifier import (
    CLASSIFIER_VERSION,
    classify_title,
)


@pytest.mark.parametrize(("title", "role", "seniority"), (
    ("Chief Procurement Officer", "procurement", "executive"),
    ("VP, Global Supply Chain", "supply_chain", "executive"),
    ("Director of Supplier Quality", "supplier_management", "director"),
    ("Manufacturing Engineering Manager", "manufacturing", "manager"),
    ("Senior Mechanical Engineer", "engineering", "individual"),
    ("Operations Supervisor", "operations", "manager"),
    ("Customer Success Wizard", "unclassified", "unclassified"),
    (None, "unclassified", "unclassified"),
))
def test_fake_titles_are_classified_by_versioned_explicit_rules(title, role, seniority):
    result = classify_title(title)
    assert (result.role_family, result.seniority_tier, result.classifier_version) == (role, seniority, CLASSIFIER_VERSION)


def test_role_precedence_is_deterministic_for_cross_function_title():
    assert classify_title("Supplier Quality Engineering Director").role_family == "supplier_management"
