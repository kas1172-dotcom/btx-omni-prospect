"""Explicit, destination-checked import of reviewed private workbook references."""
import argparse
import json

from sqlalchemy.engine import make_url

from btx_omni.core.config import Settings
from btx_omni.core.release import database_compatibility
from btx_omni.persistence.database import create_database_engine
from btx_omni.persistence.reference_fields import ReferenceFieldRepository
from btx_omni.providers.research.reference_data import (
    PRIVATE_REFERENCE_SHA256,
    load_private_reference_fields,
)
from btx_omni.providers.sample.environment import build_sample_environment


def import_reference_fields(settings, *, expected_host, expected_database, apply=False, expected_revision=None):
    url = make_url(settings.database_url)
    if settings.data_mode != 'SAMPLE' or url.get_backend_name() != 'postgresql' or url.host != expected_host or url.database != expected_database:
        raise ValueError('Reference import requires the explicitly reviewed SAMPLE PostgreSQL destination.')
    engine = create_database_engine(settings)
    try:
        compatibility = database_compatibility(engine)
        if compatibility['state'] != 'CURRENT':
            raise ValueError('Qualify the required schema before importing reference fields.')
        package = load_private_reference_fields()
        report = ReferenceFieldRepository(engine).import_package(package,
            canonical_account_ids={a.id for a in build_sample_environment().accounts}, apply=apply, expected_revision=expected_revision)
        return {**report, 'input_sha256': PRIVATE_REFERENCE_SHA256, 'database_revision': compatibility['migration_revision']}
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-revision')
    args = parser.parse_args()
    try:
        result = import_reference_fields(Settings(), **vars(args))
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
