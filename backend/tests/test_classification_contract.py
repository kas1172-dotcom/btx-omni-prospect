"""Classification records reject unscoped or mislabeled values before scoring."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from btx_omni.core.classification import Classification
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.modules.classification.records import ClassificationProvenance, FactorClassification


NOW = datetime(2026, 9, 20, tzinfo=UTC)


def provenance(*, mode=DataMode.SAMPLE, synthetic=True):
    return ClassificationProvenance("sample-test", "evidence-1", None, NOW, NOW,
                      Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED,
                      mode, synthetic)


def record(method="DETERMINISTIC"):
    authored = method == "SYNTHETIC_AUTHORED"
    return FactorClassification(
        "classification-1", "opportunity", "opportunity-1", "opportunity_priority",
        "addressable_btx_work.cross_bu_applicability", "BIN", "ONE_BU", None,
        "CURRENT", method, None if authored else "classifier-v1", "BTX_SCORING_RUBRIC_V2.0",
        ("evidence-1",), (), "sample_fixture_author" if authored else None,
        NOW if authored else None, "Explicit SAMPLE assumption for this opportunity." if authored else None,
        NOW, NOW, provenance(),
    )


def test_valid_deterministic_and_authored_records():
    assert record().method == "DETERMINISTIC"
    authored = record("SYNTHETIC_AUTHORED")
    assert authored.bin_value == "ONE_BU"
    assert authored.provenance.truth_class == "POC_SCENARIO"


def test_deterministic_requires_evidence():
    with pytest.raises(ValueError, match="evidence"):
        replace(record(), evidence_ids=())


def test_authored_requires_note():
    with pytest.raises(ValueError, match="note"):
        replace(record("SYNTHETIC_AUTHORED"), note=None)


def test_one_value_kind_only():
    with pytest.raises(ValueError, match="exactly one|one value"):
        replace(record(), raw_input={"state": "ONE_BU"})


@pytest.mark.parametrize("mode,synthetic", [(DataMode.CONNECTED, False), (DataMode.SAMPLE, False)])
def test_authored_cannot_be_connected_or_non_synthetic(mode, synthetic):
    with pytest.raises(ValueError, match="SAMPLE/synthetic"):
        replace(record("SYNTHETIC_AUTHORED"), provenance=provenance(mode=mode, synthetic=synthetic))
