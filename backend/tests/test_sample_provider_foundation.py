import json
from datetime import UTC, datetime

import pytest

from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.scoring.account_attractiveness import AccountAttractivenessInputs, calculate_account_attractiveness
from btx_omni.providers.research import _catalog_support
from btx_omni.providers.research.programs import load_programs
from btx_omni.providers.research.components import load_component_classes
from btx_omni.providers.sample.environment import build_sample_environment


def test_catalog_schema_version_is_rejected(tmp_path, monkeypatch) -> None:
    (tmp_path / "btx_program_catalog.json").write_text(json.dumps({"schema_version": "9.0"}))
    monkeypatch.setattr(_catalog_support, "RESEARCH_DIR", tmp_path)
    with pytest.raises(ValueError, match="schema_version"):
        load_programs(account_ids=set())


def test_component_foreign_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown business unit"):
        load_component_classes(business_unit_ids=set())


def test_complete_sample_provider_links_and_provenance() -> None:
    sample = build_sample_environment()
    accounts = {item.id for item in sample.accounts}
    programs = {item.id for item in sample.programs}
    components = {item.id for item in sample.component_classes}
    units = {item.id for item in sample.business_units}
    quotes = {item.id for item in sample.quotes}
    companies = {item.id for item in sample.crm_companies}
    assert len(accounts) == 34 and len(sample.rich_scenarios) == 12
    assert all(item.research_account_id in accounts for item in sample.rich_scenarios.values())
    assert all(item.account_id in accounts and item.business_unit in units and item.program_id in programs for item in sample.quotes)
    assert all(item.quote_id in quotes and item.account_id in accounts and item.component_class_id in components and item.program_id in programs for item in sample.orders if item.quote_id)
    assert all(item.from_account_id in accounts and item.to_account_id in accounts and (item.program_id is None or item.program_id in programs) for item in sample.relationship_edges)
    assert all(item.company_id in companies for item in sample.crm_contacts + sample.crm_deals + sample.crm_activities)
    assert all(item.provenance.source_record_id and item.provenance.synthetic for item in sample.quotes + sample.orders + sample.crm_companies)


def test_monthly_history_and_runtime_workflow_are_composed() -> None:
    sample = build_sample_environment()
    context = next(item for item in sample.commercial_contexts if item.account_id == "lockheed-martin")
    assert len(context.monthly_history) >= 12
    assert sum(item.revenue_minor or 0 for item in context.monthly_history) == context.ttm_revenue_minor
    score = calculate_account_attractiveness(AccountAttractivenessInputs(sample.scoring_inputs["lockheed-martin"]), evidence_ids=("test",), calculated_at=datetime(2026, 8, 31, tzinfo=UTC))
    assert score.score is not None
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, orders=sample.orders, observed_at=datetime(2026, 8, 31, tzinfo=UTC))
    assert CommercialAlertKind.OVERDUE_ORDER in {item.type for item in alerts}
