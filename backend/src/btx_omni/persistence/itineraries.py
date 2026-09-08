from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import Engine, insert, select, update

from btx_omni.persistence.models import seller_itineraries


class ItineraryConflict(ValueError):
    pass


class ItineraryRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _result(row) -> dict:
        payload = json.loads(row.payload)
        return {
            "id": row.id,
            "title": row.title,
            **payload,
            "version": row.version,
            "created_at": row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
            "updated_at": row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at,
        }

    def get(self, user_id: str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(seller_itineraries).where(seller_itineraries.c.user_id == user_id)
            ).first()
        return self._result(row) if row else None

    def save(
        self,
        *,
        user_id: str,
        title: str,
        payload: dict,
        idempotency_key: str,
        expected_version: int | None,
        now: datetime,
    ) -> dict:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = sha256(json.dumps([title, canonical], separators=(",", ":")).encode()).hexdigest()
        identifier = f"itinerary-{sha256(user_id.encode()).hexdigest()[:20]}"
        with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            row = connection.execute(
                select(seller_itineraries)
                .where(seller_itineraries.c.user_id == user_id)
                .with_for_update()
            ).first()
            if row:
                if row.idempotency_key == idempotency_key:
                    if row.payload_hash != fingerprint:
                        raise ItineraryConflict("Idempotency key was already used for different itinerary content.")
                    return self._result(row)
                if expected_version != row.version:
                    raise ItineraryConflict("Itinerary changed; reload it before saving.")
                next_version = row.version + 1
                connection.execute(
                    update(seller_itineraries)
                    .where(seller_itineraries.c.id == row.id)
                    .values(title=title, payload=canonical, payload_hash=fingerprint,
                            idempotency_key=idempotency_key, version=next_version,
                            updated_at=now)
                )
            else:
                if expected_version is not None:
                    raise ItineraryConflict("Itinerary does not exist; reload before saving.")
                next_version = 1
                connection.execute(insert(seller_itineraries).values(
                    id=identifier, user_id=user_id, title=title, payload=canonical,
                    payload_hash=fingerprint, idempotency_key=idempotency_key,
                    version=next_version, created_at=now, updated_at=now,
                ))
            saved = connection.execute(
                select(seller_itineraries).where(seller_itineraries.c.id == identifier)
            ).one()
        return self._result(saved)
