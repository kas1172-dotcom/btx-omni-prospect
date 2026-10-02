"""New catalog fields require a retained, renamed, or documented-drop disposition."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from btx_omni.domain.btx import BtxBusinessUnit, BtxFacility
from btx_omni.domain.capabilities import Capability
from btx_omni.domain.programs import ComponentClass, Program
from btx_omni.providers.research import btx_profile, capabilities, components, programs

RESEARCH = Path(__file__).resolve().parents[2] / "docs" / "research"


@pytest.mark.parametrize(
    ("filename", "collection", "model", "aliases", "dropped"),
    [
        ("btx_component_taxonomy.json", "component_classes", ComponentClass, components.FIELD_ALIASES, components.DROPPED_FIELDS),
        ("btx_program_catalog.json", "programs", Program, programs.FIELD_ALIASES, programs.DROPPED_FIELDS),
        ("btx_capability_catalog.json", "bu_capabilities", Capability, capabilities.FIELD_ALIASES, capabilities.DROPPED_FIELDS),
        ("btx_company_profile.json", "business_units", BtxBusinessUnit, btx_profile.FIELD_ALIASES["business_units"], btx_profile.DROPPED_FIELDS["business_units"]),
        ("btx_company_profile.json", "btx_facilities", BtxFacility, btx_profile.FIELD_ALIASES["btx_facilities"], btx_profile.DROPPED_FIELDS["btx_facilities"]),
    ],
)
def test_every_source_field_has_a_disposition(filename, collection, model, aliases, dropped):
    rows = json.loads((RESEARCH / filename).read_text())[collection]
    source_fields = set().union(*(row.keys() for row in rows))
    model_fields = {field.name for field in fields(model)}
    assert set(aliases.values()) <= model_fields
    undecided = source_fields - model_fields - set(aliases) - set(dropped)
    assert not undecided, f"{filename}:{collection} has undecided source fields: {sorted(undecided)}"
    assert not set(dropped) & model_fields, f"{filename}:{collection} declares retained fields as dropped"
    assert all(dropped.values()), f"{filename}:{collection} has a drop without a reason"
