from pathlib import Path
from shutil import copy2

import pytest

from btx_omni.providers.research import _catalog_support, ingestion
from btx_omni.providers.sample.environment import build_sample_environment

REPOSITORY_ROOT = Path(__file__).parents[2]
RESEARCH_SOURCE = REPOSITORY_ROOT / "docs" / "research"
RUNTIME_RESEARCH_FILES = (
    "btx_capability_catalog.json",
    "btx_company_profile.json",
    "btx_component_taxonomy.json",
    "btx_program_catalog.json",
    "btx_public_facility_feed_enrichment.json",
    "btx_relationship_edges.json",
    "btx_research_integration_manifest.json",
    "btx_researched_account_universe.json",
    "btx_researched_contacts.json",
    "btx_sample_commercial_context.json",
    "btx_sample_hubspot_crm.json",
    "btx_sample_orders.json",
    "btx_sample_paperless_quotes.json",
    "btx_sample_priority_customer_scenarios.json",
    "btx_usaspending_recipient_identities.json",
)


def _stage_runtime_research(tmp_path: Path, filenames: tuple[str, ...] = RUNTIME_RESEARCH_FILES) -> Path:
    research_dir = tmp_path / "docs" / "research"
    research_dir.mkdir(parents=True)
    for filename in filenames:
        copy2(RESEARCH_SOURCE / filename, research_dir / filename)
    return research_dir


def _use_staged_research(monkeypatch, research_dir: Path) -> None:
    monkeypatch.setattr(_catalog_support, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(ingestion, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(ingestion, "ACCOUNT_FILE", research_dir / "btx_researched_account_universe.json")
    monkeypatch.setattr(ingestion, "CONTACT_FILE", research_dir / "btx_researched_contacts.json")
    monkeypatch.setattr(ingestion, "MANIFEST_FILE", research_dir / "btx_research_integration_manifest.json")
    monkeypatch.setattr(ingestion, "FACILITY_FILE", research_dir / "btx_public_facility_feed_enrichment.json")
    monkeypatch.setattr(ingestion, "USASPENDING_RECIPIENT_FILE", research_dir / "btx_usaspending_recipient_identities.json")


def test_production_style_research_assets_initialize_the_sample_runtime(tmp_path, monkeypatch) -> None:
    research_dir = _stage_runtime_research(tmp_path)
    _use_staged_research(monkeypatch, research_dir)

    environment = build_sample_environment()

    assert environment.accounts
    assert environment.programs
    assert environment.researched_accounts


def test_missing_required_research_asset_fails_without_synthetic_substitution(tmp_path, monkeypatch) -> None:
    missing = "btx_researched_account_universe.json"
    research_dir = _stage_runtime_research(tmp_path, tuple(item for item in RUNTIME_RESEARCH_FILES if item != missing))
    _use_staged_research(monkeypatch, research_dir)

    with pytest.raises(FileNotFoundError, match=missing):
        build_sample_environment()
