from sqlalchemy import Engine, insert

from btx_omni.persistence.models import (
    accounts,
    external_ranks,
    facilities,
    identity_mappings,
    metadata,
)
from btx_omni.providers.sample.environment import SampleEnvironment


class SampleRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def seed(self, environment: SampleEnvironment) -> None:
        with self.engine.begin() as connection:
            connection.execute(insert(accounts), [{"id": item.id, "name": item.legal_name, "relationship": item.relationship.value, "domain": item.domain} for item in environment.accounts])
            connection.execute(insert(facilities), [{"id": item.id, "account_id": item.account_id, "city": item.city, "region": item.region, "latitude": str(item.latitude), "longitude": str(item.longitude)} for item in environment.facilities])
            connection.execute(insert(external_ranks), [{"account_id": item.account_id, "industry": item.industry, "rank": item.rank, "source": item.source} for item in environment.ranks])
            connection.execute(insert(identity_mappings), [{"source_key": key, "account_id": value} for key, value in environment.identity_map.items()])
