"""Durable canonical Programs composed into the existing Program catalog."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import Connection, Engine, delete, insert, select

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.programs import Program
from btx_omni.persistence.durable_accounts import _provenance, _provenance_payload
from btx_omni.persistence.models import durable_canonical_programs


@dataclass(frozen=True)
class DurableCanonicalProgram:
    program: Program
    identity_key: str
    originating_candidate_id: str | None
    created_at: datetime
    promoted_at: datetime | None = None
    promotion_provenance: Provenance | None = None


def _normal(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _identity_key(name: str, provenance: Provenance) -> str:
    return f"source-name:{provenance.source_system}:{_normal(name)}"


def _program_id(identity_key: str) -> str:
    return f"program-{sha256(identity_key.encode()).hexdigest()[:24]}"


def _timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _payload(program: Program) -> str:
    return json.dumps({
        "id": program.id,
        "account_id": program.account_id,
        "name": program.name,
        "system": program.system,
        "evidence_state": program.evidence_state.value,
        "provenance": _provenance_payload(program.provenance),
    }, sort_keys=True)


def _from_payload(payload: str) -> Program:
    value = json.loads(payload)
    return Program(
        value["id"], value.get("account_id"), value["name"], value.get("system"),
        EvidenceState(value["evidence_state"]), _provenance(value["provenance"]),
    )


class DurableCanonicalProgramRepository:
    """The sole durable Program write/read boundary; it never infers Program facts."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def programs(self) -> tuple[DurableCanonicalProgram, ...]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(durable_canonical_programs).order_by(durable_canonical_programs.c.id)).mappings()
            return tuple(DurableCanonicalProgram(
                _from_payload(row["program_payload"]), row["identity_key"], row["originating_candidate_id"], _timestamp(row["created_at"]),
                _timestamp(row["promoted_at"]) if row["promoted_at"] else None,
                _provenance(json.loads(row["promotion_provenance"])) if row["promotion_provenance"] else None,
            ) for row in rows)

    def create_program(
        self, *, name: str, provenance: Provenance, canonical_account_id: str | None = None, system: str | None = None,
        originating_candidate_id: str | None = None, curated_programs: tuple[Program, ...] = (), canonical_account_ids: frozenset[str] = frozenset(),
        created_at: datetime | None = None, promoted_at: datetime | None = None, promotion_provenance: Provenance | None = None,
        connection: Connection | None = None,
    ) -> DurableCanonicalProgram:
        if not name.strip():
            raise ValueError("durable canonical Programs require an evidence-backed name.")
        if provenance.data_mode is not DataMode.CONNECTED or provenance.synthetic:
            raise ValueError("durable canonical Programs require non-synthetic connected public provenance.")
        if canonical_account_id is not None and canonical_account_id not in canonical_account_ids:
            raise ValueError("durable Program Account association must reference an existing canonical Account.")
        identity_key = _identity_key(name, provenance)
        now = created_at or provenance.recorded_at
        program = Program(_program_id(identity_key), canonical_account_id, name, system, EvidenceState.CONFIRMED, provenance)
        result = DurableCanonicalProgram(program, identity_key, originating_candidate_id, now, promoted_at, promotion_provenance)
        if any(item.id == program.id or item.name.casefold() == name.casefold() for item in curated_programs):
            raise ValueError("exact canonical Program identity collision prevents durable Program creation.")
        if connection is None:
            existing = self.programs()
        else:
            rows = connection.execute(select(durable_canonical_programs).order_by(durable_canonical_programs.c.id)).mappings()
            existing = tuple(DurableCanonicalProgram(
                _from_payload(row["program_payload"]), row["identity_key"], row["originating_candidate_id"], _timestamp(row["created_at"]),
                _timestamp(row["promoted_at"]) if row["promoted_at"] else None,
                _provenance(json.loads(row["promotion_provenance"])) if row["promotion_provenance"] else None,
            ) for row in rows)
        matched = next((item for item in existing if item.identity_key == identity_key), None)
        if matched:
            if matched.program.name == name and matched.program.account_id == canonical_account_id and matched.program.system == system and matched.originating_candidate_id == originating_candidate_id:
                return matched
            raise ValueError("exact canonical Program identity collision prevents durable Program creation.")
        if any(item.program.name.casefold() == name.casefold() or item.program.id == program.id for item in existing):
            raise ValueError("exact canonical Program identity collision prevents durable Program creation.")
        def persist(target: Connection) -> None:
            target.execute(delete(durable_canonical_programs).where(durable_canonical_programs.c.id == program.id))
            target.execute(insert(durable_canonical_programs).values(
                id=program.id, identity_key=identity_key, account_id=canonical_account_id, name=name, system=system,
                program_payload=_payload(program), originating_candidate_id=originating_candidate_id, created_at=now,
                promoted_at=promoted_at, promotion_provenance=json.dumps(_provenance_payload(promotion_provenance)) if promotion_provenance else None,
            ))
        if connection is None:
            with self.engine.begin() as target:
                persist(target)
        else:
            persist(connection)
        return result
