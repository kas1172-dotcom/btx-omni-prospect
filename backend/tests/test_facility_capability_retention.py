"""Authored SAMPLE facility operations remain labeled, consistent, and optional."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from btx_omni.domain.common import DataMode
from btx_omni.providers.research import btx_profile
from btx_omni.providers.sample.environment import build_sample_environment

PROFILE = Path(__file__).resolve().parents[2] / "docs" / "research" / "btx_company_profile.json"


def test_five_facility_overlays_retain_bu_constraints_and_capacity_arithmetic():
    environment = build_sample_environment()
    units = {unit.id: unit for unit in environment.business_units}
    assert len(environment.btx_facilities) == 5
    expiries = [cert.expires_on for facility in environment.btx_facilities for cert in facility.certifications]
    assert any(date(2026, 9, 20) < expiry <= date(2027, 9, 20) for expiry in expiries)
    assert any(date(2027, 9, 20) < expiry <= date(2028, 12, 31) for expiry in expiries)
    for facility in environment.btx_facilities:
        unit = units[facility.business_unit_id]
        assert facility.data_mode == DataMode.SAMPLE
        assert facility.synthetic is True
        assert facility.source == "Authored SAMPLE operational record"
        assert facility.certifications and facility.certified_processes and facility.capacity
        assert {cert.name for cert in facility.certifications} <= set(unit.certifications)
        assert {process.process for process in facility.certified_processes} <= set(unit.processes)
        for process in facility.certified_processes:
            assert process.certification_required in {cert.name for cert in facility.certifications}
        assert facility.capacity.work_centers
        for center in facility.capacity.work_centers:
            assert center.process in unit.processes
            assert center.nominal_hours_per_week == center.machine_count * center.shifts_per_day * center.hours_per_shift * center.operational_days_per_week
            assert center.available_hours_next_90d == center.nominal_hours_per_week * 13 - center.committed_hours_next_90d
            assert center.available_hours_next_90d <= center.nominal_hours_per_week * 90 / 7
            assert 0.0 <= center.utilisation_pct <= 1.0


def test_business_unit_attributes_retain_existing_source_values():
    source_rows = {row["id"]: row for row in json.loads(PROFILE.read_text())["business_units"]}
    units = build_sample_environment().business_units
    for unit in units:
        row = source_rows[unit.id]
        assert unit.legal_name == row.get("legal_name")
        assert unit.employees == row.get("employees")
        assert unit.footprint_sqft == row.get("footprint_sqft")
        assert unit.founded == row.get("founded")
        assert unit.industries_served == tuple(row.get("industries_served") or ())
        assert unit.known_products == tuple(row.get("known_products") or ())


def test_missing_operational_fields_default_without_invented_data(monkeypatch):
    payload = copy.deepcopy(json.loads(PROFILE.read_text()))
    row = payload["btx_facilities"][0]
    for key in ("certifications", "certified_processes", "capacity", "data_mode", "synthetic", "source"):
        row.pop(key)
    monkeypatch.setattr(btx_profile, "document", lambda _: payload)
    facility = btx_profile.load_btx_facilities(business_unit_ids={unit["id"] for unit in payload["business_units"]})[0]
    assert facility.certifications == ()
    assert facility.certified_processes == ()
    assert facility.capacity is None
    assert (facility.data_mode, facility.synthetic, facility.source) == (None, None, None)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("nominal_hours_per_week", 1, "nominal_hours_per_week"),
        ("available_hours_next_90d", 999999, "90-day nominal capacity"),
        ("utilisation_pct", 1.1, "utilisation_pct"),
        ("committed_hours_next_90d", 1, "13-week nominal hours"),
    ],
)
def test_capacity_validation_names_facility_and_constraint(monkeypatch, field, value, message):
    payload = copy.deepcopy(json.loads(PROFILE.read_text()))
    payload["btx_facilities"][0]["capacity"]["work_centers"][0][field] = value
    monkeypatch.setattr(btx_profile, "document", lambda _: payload)
    with pytest.raises(ValueError, match=f"era-elk-grove.*{message}"):
        btx_profile.load_btx_facilities(business_unit_ids={unit["id"] for unit in payload["business_units"]})


def test_certification_reference_and_sample_label_validation(monkeypatch):
    payload = copy.deepcopy(json.loads(PROFILE.read_text()))
    row = payload["btx_facilities"][0]
    row["certified_processes"][0]["certification_required"] = "not-declared"
    monkeypatch.setattr(btx_profile, "document", lambda _: payload)
    with pytest.raises(ValueError, match="era-elk-grove.*absent certification"):
        btx_profile.load_btx_facilities(business_unit_ids={unit["id"] for unit in payload["business_units"]})
    row["certified_processes"][0]["certification_required"] = row["certifications"][0]["name"]
    row["synthetic"] = False
    with pytest.raises(ValueError, match="era-elk-grove.*SAMPLE/synthetic/source"):
        btx_profile.load_btx_facilities(business_unit_ids={unit["id"] for unit in payload["business_units"]})
