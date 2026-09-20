import json
from datetime import UTC, date, datetime
from pathlib import Path

from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.relationships.network_projection import (
    project_network_graph,
    prompt_safe_network_context,
)
from btx_omni.modules.relationships.routes import RouteQuery
from btx_omni.persistence.import_commercial_sample import ACCOUNT_CROSSWALK
from btx_omni.providers.sample.environment import build_sample_environment


def sample():
    package = json.loads((Path(__file__).parents[2] / "docs" / "research" / "enriched_commercial_sample.json").read_text(encoding="utf-8"))
    accounts = {ACCOUNT_CROSSWALK[item["account_id"]]: item for item in package["accounts"]}
    return project_commercial_records(build_sample_environment(), accounts, revision="network-test")


def row(index: int = 1) -> dict[str, object]:
    return {
        "batch_id": "batch-1", "exported_at": datetime(2026, 9, 1, tzinfo=UTC),
        "owner_person_id": "owner-1", "owner_display_name": "Internal Owner",
        "person_id": f"external-{index}", "person_kind": "external",
        "display_name": f"Private Person {index}", "profile_url": f"https://private.invalid/{index}",
        "raw_company_string": "Honeywell", "raw_title": "Director of Procurement",
        "account_id": "honeywell", "resolution_method": "NORMALIZED_NAME",
        "role_family": "procurement", "seniority_tier": "director",
        "as_of": datetime(2026, 9, 1, tzinfo=UTC), "internal_person_id": "owner-1",
        "connected_on": date(2024, 1, 1), "tie_source": "LINKEDIN_CONNECTION_EXPORT",
    }


def test_network_projection_routes_and_aggregates_without_changing_rubric():
    graph, _ = project_network_graph(sample(), (row(),), tenant_id="tenant-a")
    account = graph.nodes["TENANT:tenant-a:account:honeywell"]
    assert (account.contact_count, account.senior_contact_count, account.unvalidated) == (1, 1, True)
    query = RouteQuery("TENANT:tenant-a", account.id,
                       frozenset({"TENANT:tenant-a:external_contact:external-1"}),
                       "contact_candidates", date(2026, 9, 20), frozenset({"honeywell"}),
                       deadline_seconds=1.0)
    result = graph.search(query)
    route = result["evaluated_routes"][0]
    assert route["factors"].bottleneck == 1
    assert route["factors"].evidence == 1
    assert route["factors"].freshness == 1
    assert graph.nodes[route["node_ids"][-1]].provenance_label == (
        "LinkedIn connection from Internal Owner's export dated 2026-09-01, not validated"
    )


def test_imported_pii_cannot_enter_allowlisted_model_context():
    payload = json.dumps(prompt_safe_network_context((row(),)))
    assert "Private Person" not in payload
    assert "private.invalid" not in payload
    assert "Director of Procurement" not in payload
    assert payload == json.dumps({
        "contact_count": 1,
        "role_family_counts": {"procurement": 1},
        "seniority_tier_counts": {"director": 1},
        "provenance": "LinkedIn export, not validated",
    })
