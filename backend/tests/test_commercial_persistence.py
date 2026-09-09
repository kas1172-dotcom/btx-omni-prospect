"""Real importer -> SQL -> shared projection -> API regression qualification."""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from test_commercial_ledger import small_ledger

from btx_omni.api.accounts import get_runtime
from btx_omni.api.accounts import router as accounts_router
from btx_omni.api.commercial import router as commercial_router
from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.persistence import models
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.providers.sample.environment import build_sample_environment


def importer_package():
    account = small_ledger()
    account.update(identity={"display_name": "Honeywell", "legacy_identity": {"official_domains": ["honeywell.com"]}}, contacts=[], supply_relationships=[])
    account["programs"][0].update(name="Explicit fixture program")
    account["components"][0].update(name="Explicit fixture component", program_id="p", business_unit_id="BU-ERA")
    account["quotes"][0].update(status="WON")
    account["orders"][0].update(status="PARTIAL")
    account["order_lines"][0].update(program_id="p", business_unit_id="BU-ERA", committed_date="2026-08-20")
    account["monthly_commercial_history"][0]["business_unit_allocations"][0]["business_unit_id"] = "BU-ERA"
    return {"data_mode": "SIMULATED_ENVIRONMENT", "commercial_as_of": "2026-08-31", "accounts": [account]}


def test_stored_timestamp_projection_preserves_instant_not_session_timezone():
    from datetime import UTC, datetime, timedelta, timezone

    from btx_omni.persistence.commercial_import import digest, stored_projection

    source = {'occurred_at': datetime(2025, 9, 16, tzinfo=UTC), 'payload': 'unchanged'}
    eastern = {**source, 'occurred_at': datetime(2025, 9, 15, 20, tzinfo=timezone(timedelta(hours=-4)))}
    assert digest(stored_projection(eastern, source)) == digest(source)
    naive = {**source, 'occurred_at': source['occurred_at'].replace(tzinfo=None)}
    assert digest(stored_projection(naive, source)) == digest(source)
    changed = {**eastern, 'occurred_at': eastern['occurred_at'] + timedelta(seconds=1)}
    assert digest(stored_projection(changed, source)) != digest(source)
    assert eastern['occurred_at'].utcoffset() == timedelta(hours=-4)


@pytest.fixture
def storage(tmp_path):
    url = f"sqlite:///{tmp_path / 'commercial.sqlite'}"
    engine = create_engine(url)
    models.metadata.create_all(engine)
    repo = CommercialImportRepository(engine)
    yield repo, build_sample_environment(), url
    engine.dispose()


def test_dry_run_apply_replay_corrected_record_and_reopened_connection(storage):
    repo, environment, url = storage
    package = importer_package()
    crosswalk = {"test-account": "honeywell"}
    dry = repo.import_package(package, crosswalk, environment)
    assert dry["created"] > 0 and not repo.accounts()
    applied = repo.import_package(package, crosswalk, environment, apply=True)
    assert applied["created"] == dry["created"]
    replay = repo.import_package(package, crosswalk, environment, apply=True)
    assert replay["created"] == replay["updated"] == 0
    revision = repo.revision()
    corrected = deepcopy(package)
    corrected["accounts"][0]["components"][0]["name"] = "Corrected component description"
    report = repo.import_package(corrected, crosswalk, environment, apply=True)
    assert report["created"] == report["removed"] == 0
    assert report["updated"] == 2  # source component + account revision
    repo.engine.dispose()
    reopened = CommercialImportRepository(create_engine(url))
    assert reopened.revision() != revision
    assert reopened.accounts()["honeywell"] == corrected["accounts"][0]
    reopened.engine.dispose()


def test_source_order_survives_different_sql_row_order(storage):
    from btx_omni.persistence.commercial_schema import COLLECTION_TABLES
    commercial_rfqs = COLLECTION_TABLES["rfqs"]
    repo, environment, _ = storage
    package = importer_package()
    package["accounts"][0]["rfqs"].append({"rfq_id": "r-second"})
    repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    with repo.engine.begin() as connection:
        record = dict(connection.execute(commercial_rfqs.select().where(commercial_rfqs.c.id == "r")).mappings().one())
        connection.execute(commercial_rfqs.delete().where(commercial_rfqs.c.id == "r"))
        connection.execute(insert(commercial_rfqs).values(**record))
    reconstructed = repo.accounts()["honeywell"]
    assert reconstructed == package["accounts"][0]
    replay = repo.import_package({**package, "accounts": [reconstructed]}, {"test-account": "honeywell"}, environment, apply=True)
    assert replay["created"] == replay["updated"] == 0


@pytest.mark.parametrize('apply,corrected', [(False, False), (True, False), (False, True), (True, True)])
def test_manual_owned_record_drift_blocks_replay_and_updates_without_overwrite(storage, apply, corrected):
    from sqlalchemy import update

    from btx_omni.persistence.commercial_schema import (
        COLLECTION_TABLES,
        commercial_import_runs,
    )

    repo, environment, _ = storage
    original = importer_package()
    repo.import_package(original, {'test-account': 'honeywell'}, environment, apply=True)
    before_revision = repo.revision()
    component_table = COLLECTION_TABLES['components']
    with repo.engine.begin() as connection:
        connection.execute(update(component_table).where(component_table.c.id == 'c').values(name='Independent user edit'))
        run_count = len(connection.execute(commercial_import_runs.select()).all())
    incoming = deepcopy(original)
    if corrected:
        incoming['accounts'][0]['components'][0]['name'] = 'New source correction'
    with pytest.raises(ValueError, match='changed outside this import'):
        repo.import_package(incoming, {'test-account': 'honeywell'}, environment, apply=apply)
    assert repo.revision() == before_revision
    with repo.engine.connect() as connection:
        assert connection.execute(component_table.select().where(component_table.c.id == 'c')).mappings().one()['name'] == 'Independent user edit'
        assert len(connection.execute(commercial_import_runs.select()).all()) == run_count


def test_missing_owned_record_is_not_silently_replayed_or_resurrected(storage):
    from sqlalchemy import delete

    from btx_omni.persistence.commercial_schema import COLLECTION_TABLES

    repo, environment, _ = storage
    package = importer_package()
    repo.import_package(package, {'test-account': 'honeywell'}, environment, apply=True)
    table = COLLECTION_TABLES['rfqs']
    with repo.engine.begin() as connection:
        connection.execute(delete(table).where(table.c.id == 'r'))
    with pytest.raises(ValueError, match='Owned record missing'):
        repo.import_package(package, {'test-account': 'honeywell'}, environment, apply=True)
    with repo.engine.connect() as connection:
        assert connection.execute(table.select().where(table.c.id == 'r')).first() is None


def test_stale_reviewed_import_revision_cannot_overwrite_corrected_records(storage):
    repo, environment, _ = storage
    package = importer_package()
    crosswalk = {'test-account': 'honeywell'}
    initial = repo.import_package(package, crosswalk, environment)
    repo.import_package(package, crosswalk, environment, apply=True, expected_revision=initial['prior_revision'])
    reviewed = repo.import_package(package, crosswalk, environment)
    correction = deepcopy(package)
    correction['accounts'][0]['components'][0]['name'] = 'Reviewed correction'
    repo.import_package(correction, crosswalk, environment, apply=True)
    with pytest.raises(ValueError, match='changed after review'):
        repo.import_package(package, crosswalk, environment, apply=True, expected_revision=reviewed['prior_revision'])
    assert repo.accounts()['honeywell']['components'][0]['name'] == 'Reviewed correction'


def test_unowned_collision_rolls_back_and_preserves_unrelated_data(storage):
    repo, environment, _ = storage
    with repo.engine.begin() as connection:
        connection.execute(insert(models.accounts).values(id="unrelated", name="Preserve me", relationship="PROSPECT"))
        connection.execute(insert(models.programs).values(id="p", account_id="unrelated", name="Existing unrelated program", source_system="other", source_record_id="p", evidence_state="CONFIRMED", data_mode="SAMPLE", synthetic=True))
    with pytest.raises(ValueError, match="Unowned record collision"):
        repo.import_package(importer_package(), {"test-account": "honeywell"}, environment, apply=True)
    assert repo.accounts() == {}
    with repo.engine.connect() as connection:
        assert connection.execute(models.accounts.select()).mappings().all()[0]["name"] == "Preserve me"


@pytest.mark.parametrize("crosswalk", [{}, {"test-account": "invented"}, {"test-account": "boeing"}])
def test_identity_crosswalk_is_not_name_matching(storage, crosswalk):
    repo, environment, _ = storage
    with pytest.raises(ValueError):
        repo.import_package(importer_package(), crosswalk, environment, apply=True)
    assert not repo.accounts()


def test_projection_preserves_partial_shipment_unknown_part_and_no_person_link(storage):
    repo, environment, _ = storage
    repo.import_package(importer_package(), {"test-account": "honeywell"}, environment, apply=True)
    revision, records = repo.snapshot()
    sample = project_commercial_records(environment, records, revision=revision)
    orders = [o for o in sample.orders if o.account_id == "honeywell"]
    assert len(orders) == 1 and orders[0].actual_ship_date is None
    assert orders[0].part_number is None
    context = next(c for c in sample.commercial_contexts if c.account_id == "honeywell")
    assert context.ttm_revenue_minor == 400
    assert context.ttm_bookings_minor == 1000
    assert not [c for c in sample.crm_contacts if c.account_id == "honeywell"]
    assert [o for o in sample.orders if o.account_id == "boeing"] == [o for o in environment.orders if o.account_id == "boeing"]
    RelationshipIntelligenceService(sample)


def test_multi_bu_quote_has_distinct_canonical_units_and_no_false_participation(storage):
    repo, environment, _ = storage
    package = importer_package()
    account = package["accounts"][0]
    account["components"].append({"component_id": "c2", "program_id": "p", "name": "Distinct second component", "business_unit_id": "BU-GENELMEC"})
    account["quote_lines"].append({**account["quote_lines"][0], "quote_line_id": "ql2", "component_id": "c2"})
    account["quote_revisions"][0].update(line_ids=["ql", "ql2"], total_minor=2000)
    repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    revision, records = repo.snapshot()
    sample = project_commercial_records(environment, records, revision=revision)
    quote = next(q for q in sample.quotes if q.id == "q")
    assert quote.business_unit_ids == ("era-industries", "gen-el-mec")
    graph = RelationshipIntelligenceService(sample)
    quote_edges = [h for edges in graph.adjacency.values() for h in edges if h.provenance and h.provenance.source_record_id == "q"]
    assert not any(h.relationship_type == "PARTICIPATES_IN" for h in quote_edges)
    assert {h.to_entity.id for h in quote_edges if h.relationship_type == "QUOTED_WITH" and h.to_entity.kind == "business_unit"} == {"era-industries", "gen-el-mec"}


def test_real_api_readback_revision_invalidation_and_account_scoping(storage):
    repo, environment, url = storage
    package = importer_package()
    repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    runtime = PocRuntime(Settings(database_url=url, commercial_durable_state_enabled=True, _env_file=None))
    app = FastAPI()
    app.include_router(accounts_router, prefix="/api")
    app.include_router(commercial_router, prefix="/api")
    app.dependency_overrides[get_runtime] = lambda: runtime
    client = TestClient(app)
    body = client.get("/api/accounts/honeywell").json()
    assert body["commercial_ledger"]["ttm"]["revenue_minor"] == 400
    assert body["paperless_quotes"][0]["id"] == "q"
    assert next(a for a in client.get("/api/accounts").json()["accounts"] if a["id"] == "honeywell")["is_rich_scenario"]
    assert client.get("/api/accounts/honeywell/commercial/payments?record_id=pay").json()["records"][0]["amount_minor"] == 150
    assert client.get("/api/accounts/boeing/commercial/payments?record_id=pay").status_code == 404
    source = client.get('/api/accounts/honeywell/commercial/source_package').json()['reference']
    assert source['availability'] == 'MATCHED_PERSISTED_IMPORT'
    assert source['source_metadata'] == {k: v for k, v in package.items() if k != 'accounts'}
    old_revision = body["commercial_ledger"]["revision"]
    package["accounts"][0]["components"][0]["name"] = "Current corrected component"
    repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    body = client.get("/api/accounts/honeywell").json()
    assert body["commercial_ledger"]["revision"] != old_revision
    assert body["customer_360"]["components"][0]["name"] == "Current corrected component"
    updated_source = client.get('/api/accounts/honeywell/commercial/source_package').json()['reference']
    assert updated_source['account_source_version'] != source['account_source_version']
    assert updated_source['import_run_id'] != source['import_run_id']
    assert repo.source_package('boeing', source['account_source_version'])['availability'] == 'NO_MATCHING_IMPORT_METADATA_IN_BOUNDED_AUDIT'
    runtime.settings.environment = "production"
    assert client.get("/api/accounts/honeywell/commercial/payments").status_code == 401


def test_replacing_internal_scenarios_never_suppresses_existing_public_sources():
    from dataclasses import replace
    from types import SimpleNamespace

    from btx_omni.api.intelligence_projection import intelligence_signals

    base = build_sample_environment()
    def runtime(sample):
        return SimpleNamespace(environment=lambda: sample, monitor=SimpleNamespace(events={}))
    before = intelligence_signals(runtime(base))
    after = intelligence_signals(runtime(replace(base, rich_scenarios={}, priority_scenarios={})))
    assert before == after
    assert any(signal['account_id'] == 'lockheed-martin' for signal in after)
    assert all(signal['data_mode'] == 'CURATED_PUBLIC' for signal in after)


def test_durable_mode_fails_closed_without_import(storage):
    _, _, url = storage
    with pytest.raises(ValueError, match="requires a qualified import"):
        PocRuntime(Settings(database_url=url, commercial_durable_state_enabled=True, _env_file=None))


def test_omitted_records_require_explicit_retraction_not_silent_stale_readback(storage):
    repo, environment, _ = storage
    package = importer_package()
    package["accounts"][0]["contacts"] = [{"contact_id": "public-person", "title": "Candidate only"}]
    repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    revision = repo.revision()
    package["accounts"][0]["contacts"] = []
    with pytest.raises(ValueError, match="Explicit retraction required"):
        repo.import_package(package, {"test-account": "honeywell"}, environment, apply=True)
    assert repo.revision() == revision
    assert repo.accounts()["honeywell"]["contacts"][0]["contact_id"] == "public-person"
