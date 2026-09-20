"""Explicit operator import of the versioned SAMPLE ledger; dry-run by default.

Never runs on application startup. Schema migration and backup are separate gates.
"""
import argparse
import json
from hashlib import sha256

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from btx_omni.core.config import Settings
from btx_omni.core.release import REQUIRED_SCHEMA_REVISION
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.providers.research._catalog_support import RESEARCH_DIR
from btx_omni.providers.sample.environment import build_sample_environment

INPUT_SHA256 = 'b9ff27965e2716abab313f840de903191617c4da24d8fd8df7bf999c868bcd2e'
ACCOUNT_CROSSWALK = {
    'ACC-HONEYWELL': 'honeywell', 'ACC-BOEING': 'boeing', 'ACC-KLA': 'kla',
    'ACC-SPACEX': 'spacex', 'ACC-INTUITIVE': 'intuitive-surgical',
    'ACC-LOCKHEED': 'lockheed-martin', 'ACC-WOODWARD': 'woodward',
    'ACC-NORTHROP': 'northrop-grumman', 'ACC-HUXWRX': 'huxwrx',
    'ACC-EATON': 'eaton', 'ACC-EMERSON': 'emerson',
}


def load_release_sample() -> dict:
    raw = (RESEARCH_DIR / 'enriched_commercial_sample.json').read_bytes()
    if sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError('Commercial runtime input does not match the reviewed release hash.')
    package = json.loads(raw)
    if {account['account_id'] for account in package['accounts']} != set(ACCOUNT_CROSSWALK):
        raise ValueError('Runtime sample identities differ from the reviewed account-only crosswalk.')
    return package


def import_release_sample(settings: Settings, *, apply: bool = False, expected_host: str | None = None,
                          expected_database: str | None = None, expected_revision: str | None = None) -> dict:
    if settings.data_mode != 'SAMPLE':
        raise ValueError('Only SAMPLE imports are supported.')
    url = make_url(settings.database_url)
    if url.get_backend_name() != 'postgresql':
        raise ValueError('Release import requires a qualified PostgreSQL destination.')
    if not expected_host or not expected_database or url.host != expected_host or url.database != expected_database:
        raise ValueError('The configured database must match the explicitly reviewed host and database name.')
    if apply and not expected_revision:
        raise ValueError('Apply requires the prior_revision from a reviewed dry-run.')
    package = load_release_sample()
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            version = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        if version != REQUIRED_SCHEMA_REVISION:
            raise ValueError('Run the release migration qualification before importing this sample.')
        repository = CommercialImportRepository(engine)
        result = repository.import_package(package, ACCOUNT_CROSSWALK, build_sample_environment(),
                                           apply=apply, data_mode=settings.data_mode, expected_revision=expected_revision)
        return {**result, 'input_sha256': INPUT_SHA256, 'database_version': version,
                'repository': 'kas1172-dotcom/btx-omni-prospect', 'current_revision': repository.revision()}
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--expected-revision')
    args = parser.parse_args()
    try:
        report = import_release_sample(Settings(), apply=args.apply, expected_host=args.expected_host,
                                       expected_database=args.expected_database, expected_revision=args.expected_revision)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
