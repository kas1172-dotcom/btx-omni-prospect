"""Expanded facility capability overlays stay bounded by BU declarations and SAMPLE labels."""

from __future__ import annotations

from btx_omni.domain.common import DataMode
from btx_omni.providers.sample.environment import build_sample_environment

SOURCE_NOTE = "Authored SAMPLE operational record"
FACILITY_COUNTS = {
    "era-elk-grove": (7, 4, 18),
    "era-wheeling": (5, 3, 9),
    "era-arizona": (3, 2, 6),
    "apm-rochester": (5, 3, 11),
    "a1j-san-jose": (4, 3, 7),
}


def test_bu_and_facility_capabilities_are_non_degenerate():
    environment = build_sample_environment()
    units = {unit.id: unit for unit in environment.business_units}
    assert {facility.id for facility in environment.btx_facilities} == set(FACILITY_COUNTS)
    for unit_id in ("era-industries", "addison-precision", "a1j-technologies"):
        unit = units[unit_id]
        assert len(unit.processes) >= 8
        assert len(unit.certifications) >= 4
    for unit_id in ("era-industries", "addison-precision"):
        unit = units[unit_id]
        assert (unit.data_mode, unit.synthetic, unit.source) == (DataMode.SAMPLE, True, SOURCE_NOTE)
    assert "NADCAP Brazing" in units["era-industries"].certifications
    assert "inspection (CMM)" in units["addison-precision"].processes
    assert "NADCAP Nonconventional Machining" in units["addison-precision"].certifications

    for facility in environment.btx_facilities:
        unit = units[facility.business_unit_id]
        process_count, certification_count, machine_count = FACILITY_COUNTS[facility.id]
        assert len(facility.certified_processes) == process_count >= 3
        assert len(facility.certifications) == certification_count >= 2
        assert sum(center.machine_count for center in facility.capacity.work_centers) == machine_count
        assert (facility.data_mode, facility.synthetic, facility.source) == (DataMode.SAMPLE, True, SOURCE_NOTE)
        assert {cert.name for cert in facility.certifications} <= set(unit.certifications)
        assert {process.process for process in facility.certified_processes} <= set(unit.processes)


def test_each_nested_operational_record_is_labeled_and_internally_consistent():
    for facility in build_sample_environment().btx_facilities:
        certification_names = {cert.name for cert in facility.certifications}
        for cert in facility.certifications:
            assert (cert.data_mode, cert.synthetic, cert.source) == (DataMode.SAMPLE, True, SOURCE_NOTE)
        for process in facility.certified_processes:
            assert (process.data_mode, process.synthetic, process.source) == (DataMode.SAMPLE, True, SOURCE_NOTE)
            assert 3 <= len(process.materials_supported) <= 8
            if process.certification_required is not None:
                assert process.certification_required in certification_names
        for center in facility.capacity.work_centers:
            assert (center.data_mode, center.synthetic, center.source) == (DataMode.SAMPLE, True, SOURCE_NOTE)
            assert center.process in {process.process for process in facility.certified_processes}
            assert center.nominal_hours_per_week == center.machine_count * center.shifts_per_day * center.hours_per_shift * center.operational_days_per_week
            assert center.available_hours_next_90d == center.nominal_hours_per_week * 13 - center.committed_hours_next_90d
            assert center.available_hours_next_90d <= center.nominal_hours_per_week * 13
            assert 0.0 <= center.utilisation_pct <= 1.0
