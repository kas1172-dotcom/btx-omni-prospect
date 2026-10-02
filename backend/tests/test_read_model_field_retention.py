"""Research-catalog technical fields survive the SAMPLE read-model projection."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from btx_omni.providers.research import btx_profile, capabilities, components, programs
from btx_omni.providers.sample.environment import build_sample_environment

RESEARCH = Path(__file__).resolve().parents[2] / "docs" / "research"


def _catalog(filename: str) -> dict:
    return json.loads((RESEARCH / filename).read_text())


def test_loaded_research_fields_match_source_json_and_are_deterministic() -> None:
    first = build_sample_environment()
    second = build_sample_environment()

    component_row = _catalog("btx_component_taxonomy.json")["component_classes"][0]
    component = next(item for item in first.component_classes if item.id == component_row["id"])
    assert component.typical_materials == tuple(component_row["typical_materials"])
    assert component.typical_processes == tuple(component_row["typical_processes"])
    assert component.typical_tolerance == component_row["typical_tolerance"]
    assert component.typical_size_bracket == component_row["typical_size_bracket"]

    program_row = _catalog("btx_program_catalog.json")["programs"][0]
    program = next(item for item in first.programs if item.id == program_row["id"])
    assert program.expected_production_horizon_years == program_row["expected_production_horizon_years"]
    assert program.commitment_strength == program_row["commitment_strength"]
    assert program.maturity_evidence == program_row["maturity_evidence"]

    capability_row = _catalog("btx_capability_catalog.json")["bu_capabilities"][0]
    capability = next(item for item in first.capabilities if item.id == f"cap-{capability_row['bu_id']}")
    assert capability.volume_profile == tuple(capability_row["volume_profile"])
    assert capability.industries_served == tuple(capability_row["industries_served"])
    assert capability.processes == tuple(item["process"] for item in capability_row["process_families"])
    for projected, source in zip(capability.process_families, capability_row["process_families"], strict=True):
        assert projected.process == source["process"]
        assert projected.envelope_directional == source.get("envelope_directional")
        assert projected.materials_supported == tuple(source.get("materials_supported") or ())
        assert projected.tolerance_capability == source.get("tolerance_capability")
        assert projected.certifications_applicable == tuple(source.get("certifications_applicable") or ())
        assert projected.specialty_note == source.get("specialty_note")

    profile = _catalog("btx_company_profile.json")
    unit_row = profile["business_units"][0]
    unit = next(item for item in first.business_units if item.id == unit_row["id"])
    assert unit.capacity_signals == tuple(sorted(unit_row["capacity_signals"].items()))
    facility_row = profile["btx_facilities"][0]
    facility = next(item for item in first.btx_facilities if item.id == facility_row["id"])
    assert facility.source_ids == tuple(facility_row["source_ids"])

    assert first.component_classes == second.component_classes
    assert first.programs == second.programs
    assert first.capabilities == second.capabilities
    assert first.business_units == second.business_units
    assert first.btx_facilities == second.btx_facilities


def test_missing_optional_source_fields_do_not_gain_placeholder_values(monkeypatch) -> None:
    environment = build_sample_environment()
    business_unit_ids = {item.id for item in environment.business_units}
    account_ids = {item.id for item in environment.accounts}

    component_payload = copy.deepcopy(_catalog("btx_component_taxonomy.json"))
    for field in ("typical_materials", "typical_processes", "typical_tolerance", "typical_size_bracket"):
        component_payload["component_classes"][0].pop(field)
    monkeypatch.setattr(components, "document", lambda _: component_payload)
    component = components.load_component_classes(business_unit_ids=business_unit_ids)[0]
    assert (component.typical_materials, component.typical_processes) == ((), ())
    assert (component.typical_tolerance, component.typical_size_bracket) == (None, None)

    program_payload = copy.deepcopy(_catalog("btx_program_catalog.json"))
    for field in ("expected_production_horizon_years", "commitment_strength", "maturity_evidence"):
        program_payload["programs"][0].pop(field)
    monkeypatch.setattr(programs, "document", lambda _: program_payload)
    program = programs.load_programs(account_ids=account_ids)[0]
    assert (program.expected_production_horizon_years, program.commitment_strength, program.maturity_evidence) == (None, None, None)

    capability_payload = copy.deepcopy(_catalog("btx_capability_catalog.json"))
    capability_payload["bu_capabilities"][0].pop("volume_profile")
    capability_payload["bu_capabilities"][0]["process_families"][0].pop("materials_supported", None)
    monkeypatch.setattr(capabilities, "document", lambda _: capability_payload)
    capability = capabilities.load_capabilities(business_unit_ids=business_unit_ids)[0]
    assert capability.volume_profile == ()
    assert capability.process_families[0].materials_supported == ()

    profile_payload = copy.deepcopy(_catalog("btx_company_profile.json"))
    profile_payload["business_units"][0].pop("capacity_signals")
    profile_payload["btx_facilities"][0].pop("source_ids")
    monkeypatch.setattr(btx_profile, "document", lambda _: profile_payload)
    assert btx_profile.load_btx_business_units()[0].capacity_signals == ()
    assert btx_profile.load_btx_facilities(business_unit_ids=business_unit_ids)[0].source_ids == ()
