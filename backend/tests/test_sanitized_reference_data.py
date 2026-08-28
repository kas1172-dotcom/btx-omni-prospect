from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from btx_omni.app import create_app
from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.providers.research.reference_data import (
    REFERENCE_FILE,
    load_reference_import,
)
from btx_omni.providers.sample.environment import build_sample_environment

_IMPORT_SPEC = spec_from_file_location(
    "sanitized_reference_import",
    Path(__file__).parents[1] / "tools" / "import_sanitized_reference_data.py",
)
assert _IMPORT_SPEC and _IMPORT_SPEC.loader
_IMPORT_MODULE = module_from_spec(_IMPORT_SPEC)
_IMPORT_SPEC.loader.exec_module(_IMPORT_MODULE)
ALLOWED = _IMPORT_MODULE.ALLOWED
EXCLUDED = _IMPORT_MODULE.EXCLUDED
IMPORT_PROHIBITED = _IMPORT_MODULE.PROHIBITED
assert_prohibited_fields_blank = _IMPORT_MODULE.assert_prohibited_fields_blank

PROHIBITED = {
    "BTX Direct Customer Revenue (in 000's) TTM May2026",
    "Active BTX BU's with Sales TTM",
    "BTX Targeting Notes",
    "Priority Score",
}
PRIORITY_IDS = {
    "honeywell",
    "boeing",
    "kla",
    "spacex",
    "intuitive-surgical",
    "lockheed-martin",
    "woodward",
    "northrop-grumman",
    "huxwrx",
    "eaton",
    "emerson",
}


def fixture() -> dict[str, object]:
    return json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))


def test_import_schema_allowlist_and_prohibited_gate_fail_closed() -> None:
    assert ALLOWED.isdisjoint(EXCLUDED)
    assert IMPORT_PROHIBITED <= EXCLUDED
    with pytest.raises(
        ValueError, match=r"sensitive\.xlsx/Sheet1/.*/rows \[2\]"
    ) as error:
        assert_prohibited_fields_blank(
            workbook="sensitive.xlsx",
            sheet="Sheet1",
            headers=[next(iter(IMPORT_PROHIBITED))],
            rows=[(2, ["redacted nonblank value"])],
        )
    assert "redacted nonblank value" not in str(error.value)


def test_normalized_fixture_contains_only_reviewed_reference_schema() -> None:
    document = fixture()
    serialized = json.dumps(document).casefold()

    assert document["schema_version"] == "1.0"
    assert len(document["sources"]) == 6
    assert len(document["identity_audit"]) == 474
    assert not any(value.casefold() in serialized for value in PROHIBITED)
    assert all(
        source["sanitation_gate"] == "PASS_PROHIBITED_FIELDS_BLANK"
        for source in document["sources"]
    )
    assert all(
        item["identity_evidence"] == "EXACT_CORPORATE_DOMAIN"
        for item in document["identity_audit"]
    )
    assert not any(
        item["disposition"] == "AMBIGUOUS_NEEDS_REVIEW"
        for item in document["identity_audit"]
    )


def test_reference_import_preserves_ids_taxonomy_and_truth_boundaries() -> None:
    reference = load_reference_import()
    accounts = {item.id: item for item in reference.accounts}

    assert len(accounts) == 298
    assert len({item.legal_name.casefold() for item in accounts.values()}) == len(accounts)
    assert len(reference.facilities) == 392
    assert PRIORITY_IDS <= set(accounts)
    assert all(set(item.industries) <= PRIMARY_MARKETS for item in accounts.values())
    assert accounts["honeywell"].industries == ("Commercial Aerospace", "Defense")
    assert accounts["huxwrx"].industries == ()
    assert accounts["intuitive-surgical"].industries == ("Medical",)
    assert sum(item.btx_top_100 for item in accounts.values()) == 87
    assert all(
        item.btx_top_100_provenance for item in accounts.values() if item.btx_top_100
    )
    assert all(
        "UAV_REFERENCE_SEGMENT" not in item.industries for item in accounts.values()
    )
    assert all(item.relationship.value == "PUBLIC_MARKET" for item in accounts.values())


def test_environment_deduplicates_existing_priority_customers_and_preserves_ids() -> (
    None
):
    environment = build_sample_environment()
    ids = [item.id for item in environment.accounts]

    assert len(ids) == len(set(ids)) == 309
    assert PRIORITY_IDS <= set(ids)
    assert ids.count("boeing") == ids.count("kla") == ids.count("spacex") == 1
    assert len(environment.reference_facilities) == 392
    assert all(
        item.verification_state == "SANITIZED_REFERENCE_LOCATION"
        for item in environment.reference_facilities
    )
    assert all(
        item.provenance and item.provenance.source_ids
        for item in environment.reference_facilities
    )


def test_top_100_and_reference_geography_flow_through_canonical_apis() -> None:
    client = TestClient(create_app())
    accounts = client.get("/api/accounts").json()["accounts"]
    map_data = client.get("/api/map").json()
    honeywell = next(item for item in accounts if item["id"] == "honeywell")
    honeywell_map = next(
        item for item in map_data["accounts"] if item["account_id"] == "honeywell"
    )
    omni = client.post(
        "/api/omni",
        json={
            "account_id": "honeywell",
            "question": "Is Honeywell in BTX Top 100 and what do we know?",
        },
    ).json()

    assert honeywell["btx_top_100"] is True
    assert honeywell["commercial_context_state"] == "SAMPLE"
    assert honeywell["attractiveness"] is not None
    assert honeywell_map["btx_top_100"] is True
    assert honeywell_map["location_truth_state"] == "SANITIZED_REFERENCE_LOCATION"
    assert "BTX Top 100: yes" in omni["content"]
    assert "sanitized reference source" in omni["content"]
    assert "BTX commercial context is simulated" in omni["content"]
    assert not any("strategic" in json.dumps(item).casefold() for item in accounts)


def test_top_100_is_membership_not_rank_and_unsupported_classes_remain_absent() -> None:
    document = fixture()
    accounts = document["accounts"]

    assert sum(bool(item["btx_top_100"]) for item in accounts) == 87
    assert all(
        "rank" not in item and "priority" not in item and "attractiveness" not in item
        for item in accounts
    )
    assert document["unsupported_classifications"]["industry_top_100"]
    assert document["unsupported_classifications"]["strategic_partnership"]
