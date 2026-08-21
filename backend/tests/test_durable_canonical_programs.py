from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from btx_omni.api.runtime import PocRuntime
from btx_omni.core.classification import Classification
from btx_omni.core.config import Settings
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.persistence.models import metadata


def _settings(tmp_path) -> Settings:
    settings = Settings(
        _env_file=None,
        monitor_mode="live",
        monitor_durable_state_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'durable-canonical-programs.db'}",
    )
    metadata.create_all(create_engine(settings.database_url))
    return settings


def _provenance(record_id: str = "durable-program-1") -> Provenance:
    observed = datetime(2026, 8, 31, tzinfo=UTC)
    return Provenance(
        "test-authoritative-public-source", record_id, f"https://public.example.test/{record_id}", observed, observed,
        Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.CONNECTED, False,
    )


def _nexus_account(runtime: PocRuntime):
    assert runtime.durable_accounts
    account = runtime.durable_accounts.create_public_prospect(
        legal_name="Nexus Quantum Systems, Inc.", industries=("Semiconductor",), provenance=_provenance("nexus-account"),
        aliases=("Nexus Quantum",), domain="nexus.example.test", source_identifiers=(("uei", "NEXUS-UEI-001"),),
        curated_accounts=runtime.sample.accounts,
    ).account
    runtime.refresh_durable_catalog()
    return account


def _create(runtime: PocRuntime, account_id: str):
    assert runtime.durable_programs
    return runtime.durable_programs.create_program(
        name="Nexus Quantum Manufacturing Platform", canonical_account_id=account_id, system="Semiconductor manufacturing expansion",
        provenance=_provenance(), curated_programs=runtime.sample.programs,
        canonical_account_ids=frozenset(account.id for account in runtime.sample.accounts),
    )


def test_durable_canonical_program_composes_catalog_and_survives_restart(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime = PocRuntime(settings)
    curated_program_ids = tuple(item.id for item in runtime.sample.programs)
    candidate_state = runtime.monitor.repository.candidates()  # type: ignore[union-attr]
    nexus = _nexus_account(runtime)
    created = _create(runtime, nexus.id)
    replay = _create(runtime, nexus.id)
    assert replay.program.id == created.program.id
    runtime.refresh_durable_catalog()

    program = next(item for item in runtime.environment().programs if item.id == created.program.id)
    assert tuple(item.id for item in runtime.environment().programs[: len(curated_program_ids)]) == curated_program_ids
    assert sum(item.id == program.id for item in runtime.environment().programs) == 1
    assert program.account_id == nexus.id
    assert program.provenance == _provenance()
    assert runtime.monitor.catalog.resolve_program("Nexus Quantum Manufacturing Platform production award").canonical_program_id == program.id
    assert runtime.monitor.catalog.resolve_program("Nexus Quantum Manufacturing").state is ResolutionState.UNRESOLVED
    assert runtime.monitor.repository.candidates() == candidate_state  # type: ignore[union-attr]
    assert program.id not in runtime.sample.scoring_inputs
    assert not [item for item in runtime.sample.commercial_contexts if item.account_id == nexus.id]
    assert not [item for item in runtime.sample.public_facilities if item.account_id == nexus.id]

    restarted = PocRuntime(settings)
    restored = next(item for item in restarted.environment().programs if item.id == program.id)
    assert restored == program
    assert restarted.monitor.catalog.resolve_program("Nexus Quantum Manufacturing Platform").canonical_program_id == program.id


def test_durable_program_collisions_and_account_association_fail_closed(tmp_path) -> None:
    runtime = PocRuntime(_settings(tmp_path))
    nexus = _nexus_account(runtime)
    created = _create(runtime, nexus.id)
    assert runtime.durable_programs

    with pytest.raises(ValueError, match="exact canonical Program identity collision"):
        runtime.durable_programs.create_program(
            name=runtime.sample.programs[0].name, provenance=_provenance("curated-collision"),
            curated_programs=runtime.sample.programs, canonical_account_ids=frozenset(account.id for account in runtime.sample.accounts),
        )
    with pytest.raises(ValueError, match="existing canonical Account"):
        runtime.durable_programs.create_program(
            name="Unverified Owner Program", canonical_account_id="not-a-canonical-account", provenance=_provenance("bad-owner"),
            curated_programs=runtime.sample.programs, canonical_account_ids=frozenset(account.id for account in runtime.sample.accounts),
        )
    with pytest.raises(ValueError, match="exact canonical Program identity collision"):
        runtime.durable_programs.create_program(
            name="Nexus Quantum Manufacturing Platform", system="Conflicting system", provenance=_provenance(), curated_programs=runtime.sample.programs,
            canonical_account_ids=frozenset(account.id for account in runtime.sample.accounts),
        )
    assert created.program.id in {item.program.id for item in runtime.durable_programs.programs()}
