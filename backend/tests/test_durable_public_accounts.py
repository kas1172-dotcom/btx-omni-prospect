from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.app import create_app
from btx_omni.core.classification import Classification
from btx_omni.core.config import Settings
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.resolution import resolve_entity
from btx_omni.persistence.durable_accounts import DurablePublicAccountRepository
from btx_omni.persistence.models import metadata


def _settings(tmp_path) -> Settings:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'durable-public-accounts.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return settings


def _provenance() -> Provenance:
    observed = datetime(2026, 8, 31, tzinfo=UTC)
    return Provenance(
        "test-authoritative-public-source",
        "public-prospect-foundation-1",
        "https://public.example.test/nexus",
        observed,
        observed,
        Classification.PUBLIC,
        EvidenceState.CONFIRMED,
        DataMode.CONNECTED,
        False,
    )


def _create(repo: DurablePublicAccountRepository, curated) -> object:
    return repo.create_public_prospect(
        legal_name="Nexus Quantum Systems, Inc.",
        industries=("Semiconductor",),
        provenance=_provenance(),
        aliases=("Nexus Quantum",),
        domain="nexus.example.test",
        source_identifiers=(("uei", "NEXUS-UEI-001"),),
        curated_accounts=curated,
    )


def test_durable_public_prospect_composes_the_canonical_runtime_universe(tmp_path) -> None:
    settings = _settings(tmp_path)
    first_runtime = PocRuntime(settings)
    assert first_runtime.durable_accounts
    curated_ids = tuple(account.id for account in first_runtime.sample.accounts)
    created = _create(first_runtime.durable_accounts, first_runtime.sample.accounts)

    restarted = PocRuntime(settings)
    account = next(item for item in restarted.environment().accounts if item.id == created.account.id)
    assert tuple(item.id for item in restarted.environment().accounts[: len(curated_ids)]) == curated_ids
    assert sum(item.id == account.id for item in restarted.environment().accounts) == 1
    assert account.relationship is AccountRelationship.PROSPECT
    assert account.public_identity and account.public_identity.legal_name
    assert account.provenance == _provenance()
    assert restarted.durable_accounts and len(restarted.durable_accounts.accounts()) == 1
    assert account.id not in restarted.sample.scoring_inputs
    assert not [item for item in restarted.sample.commercial_contexts if item.account_id == account.id]
    assert not [item for item in restarted.sample.public_facilities if item.account_id == account.id]
    assert resolve_entity("Nexus Quantum", restarted.sample.watch_profiles).canonical_account_id == account.id
    assert RelationshipIntelligenceService(restarted.environment()).account_relationships(account.id, depth=2)["direct_relationships"] == []

    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: restarted
    client = TestClient(app)
    listed = client.get("/api/accounts")
    detail = client.get(f"/api/accounts/{account.id}")
    map_data = client.get("/api/map")
    omni = client.post("/api/omni", json={"question": "Does it have quote history?", "context": {"surface": "ACCOUNT_DETAIL", "selected_account_id": account.id}})
    assert listed.status_code == detail.status_code == map_data.status_code == omni.status_code == 200
    listed_account = next(item for item in listed.json()["accounts"] if item["id"] == account.id)
    assert listed_account["relationship"] == "PROSPECT"
    assert listed_account["attractiveness"] is None
    assert detail.json()["account_attractiveness"]["score"] is None
    assert all(item["account_id"] != account.id for item in map_data.json()["accounts"])
    assert omni.json()["context_used"]["account_id"] == account.id


def test_durable_public_account_writes_are_exact_collision_safe_and_idempotent(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime = PocRuntime(settings)
    assert runtime.durable_accounts
    created = _create(runtime.durable_accounts, runtime.sample.accounts)
    replay = _create(runtime.durable_accounts, runtime.sample.accounts)
    assert replay.account.id == created.account.id
    assert len(runtime.durable_accounts.accounts()) == 1

    with pytest.raises(ValueError, match="exact canonical identity collision"):
        runtime.durable_accounts.create_public_prospect(
            legal_name="Medtronic",
            industries=("Medical",),
            provenance=_provenance(),
            curated_accounts=runtime.sample.accounts,
        )
    with pytest.raises(ValueError, match="exact canonical identity collision"):
        runtime.durable_accounts.create_public_prospect(
            legal_name="Nexus Alias Collision, Inc.",
            industries=("Semiconductor",),
            provenance=_provenance(),
            aliases=("Medtronic",),
            curated_accounts=runtime.sample.accounts,
        )
    with pytest.raises(ValueError, match="exact canonical identity collision"):
        runtime.durable_accounts.create_public_prospect(
            legal_name="Different Nexus Entity",
            industries=("Semiconductor",),
            provenance=_provenance(),
            source_identifiers=(("uei", "NEXUS-UEI-001"),),
            curated_accounts=runtime.sample.accounts,
        )
    assert resolve_entity("Nexus Quant", runtime.sample.watch_profiles).state is ResolutionState.UNRESOLVED
