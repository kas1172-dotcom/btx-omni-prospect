from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import Engine, and_, insert, select, update

from btx_omni.persistence.models import (
    account_partnership_audit,
    account_partnership_designations,
    seller_shortlist_items,
)


class AccountPlanningConflict(ValueError):
    pass


def _hash(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _time(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class AccountPlanningRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def view(self, user_id: str) -> dict:
        with self.engine.connect() as connection:
            designation_records = connection.execute(
                select(account_partnership_designations).order_by(account_partnership_designations.c.account_id)
            ).mappings().all()
            shortlist_records = connection.execute(
                select(seller_shortlist_items).where(seller_shortlist_items.c.user_id == user_id).order_by(seller_shortlist_items.c.target_date.nulls_last(), seller_shortlist_items.c.account_id)
            ).mappings().all()
        designations = [row for row in designation_records if row["designated"]]
        shortlist = [row for row in shortlist_records if row["active"]]
        return {
            "strategic_partnerships": [{"account_id": row["account_id"], "reason": row["reason"], "version": row["version"], "updated_by": row["updated_by"], "updated_at": _time(row["updated_at"])} for row in designations],
            "shortlist": [{"id": row["id"], "account_id": row["account_id"], "kind": row["kind"], "objective": row["objective"], "target_date": row["target_date"], "version": row["version"], "created_at": _time(row["created_at"]), "updated_at": _time(row["updated_at"])} for row in shortlist],
            "partnership_records": [{"account_id": row["account_id"], "designated": row["designated"], "reason": row["reason"], "version": row["version"], "updated_by": row["updated_by"], "updated_at": _time(row["updated_at"])} for row in designation_records],
            "shortlist_records": [self._shortlist(row) for row in shortlist_records],
            "scope": "SHORTLIST_CURRENT_USER_ONLY; PARTNERSHIP_DESIGNATION_SHARED_WORKSPACE",
        }

    def designate(self, *, account_id: str, designated: bool, reason: str, actor_id: str,
                  expected_version: int | None, idempotency_key: str, now: datetime) -> dict:
        fingerprint = _hash([account_id, designated, reason])
        with self.engine.begin() as connection:
            replay = connection.execute(select(account_partnership_audit).where(account_partnership_audit.c.idempotency_key == idempotency_key)).mappings().one_or_none()
            if replay:
                if replay["payload_hash"] != fingerprint:
                    raise AccountPlanningConflict("Idempotency key was already used for another designation.")
                return {"account_id": replay["account_id"], "designated": replay["designated"], "reason": replay["reason"], "version": replay["version"], "updated_by": replay["actor_id"], "updated_at": _time(replay["occurred_at"])}
            current = connection.execute(select(account_partnership_designations).where(account_partnership_designations.c.account_id == account_id).with_for_update()).mappings().one_or_none()
            if (current and expected_version != current["version"]) or (not current and expected_version is not None):
                raise AccountPlanningConflict("Partnership designation changed; reload before saving.")
            version = (current["version"] + 1) if current else 1
            values = {"account_id": account_id, "designated": designated, "reason": reason, "version": version,
                      "updated_by": actor_id, "updated_at": now, "idempotency_key": idempotency_key, "payload_hash": fingerprint}
            if current:
                connection.execute(update(account_partnership_designations).where(account_partnership_designations.c.account_id == account_id).values(**{key: value for key, value in values.items() if key != "account_id"}))
            else:
                connection.execute(insert(account_partnership_designations).values(**values))
            connection.execute(insert(account_partnership_audit).values(id=f"partnership-audit-{sha256(idempotency_key.encode()).hexdigest()[:24]}", actor_id=actor_id, occurred_at=now, **{key: value for key, value in values.items() if key not in {"updated_by", "updated_at"}}))
        return {"account_id": account_id, "designated": designated, "reason": reason, "version": version, "updated_by": actor_id, "updated_at": now}

    def save_shortlist(self, *, user_id: str, account_id: str, kind: str, objective: str,
                       target_date: str | None, active: bool, expected_version: int | None,
                       idempotency_key: str, now: datetime) -> dict:
        fingerprint = _hash([account_id, kind, objective, target_date, active])
        identifier = f"shortlist-{sha256(f'{user_id}:{account_id}'.encode()).hexdigest()[:24]}"
        with self.engine.begin() as connection:
            row = connection.execute(select(seller_shortlist_items).where(and_(seller_shortlist_items.c.user_id == user_id, seller_shortlist_items.c.account_id == account_id)).with_for_update()).mappings().one_or_none()
            if row and row["idempotency_key"] == idempotency_key:
                if row["payload_hash"] != fingerprint:
                    raise AccountPlanningConflict("Idempotency key was already used for another shortlist change.")
                return self._shortlist(row)
            if (row and expected_version != row["version"]) or (not row and expected_version is not None):
                raise AccountPlanningConflict("Shortlist item changed; reload before saving.")
            version = (row["version"] + 1) if row else 1
            values = {"kind": kind, "objective": objective, "target_date": target_date, "active": active,
                      "version": version, "idempotency_key": idempotency_key, "payload_hash": fingerprint, "updated_at": now}
            if row:
                connection.execute(update(seller_shortlist_items).where(seller_shortlist_items.c.id == row["id"]).values(**values))
            else:
                connection.execute(insert(seller_shortlist_items).values(id=identifier, user_id=user_id, account_id=account_id, created_at=now, **values))
            saved = connection.execute(select(seller_shortlist_items).where(seller_shortlist_items.c.id == identifier)).mappings().one()
        return self._shortlist(saved)

    @staticmethod
    def _shortlist(row) -> dict:
        return {"id": row["id"], "account_id": row["account_id"], "kind": row["kind"], "objective": row["objective"], "target_date": row["target_date"], "active": row["active"], "version": row["version"], "created_at": _time(row["created_at"]), "updated_at": _time(row["updated_at"])}
