"""Explicit local/CI PostgreSQL fixture setup; never a deployed SAMPLE importer."""
import json
import subprocess
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from btx_omni.core.config import Settings
from btx_omni.modules.markets.g17 import parse_g17
from btx_omni.modules.markets.registry import G17_URL
from btx_omni.persistence.import_commercial_sample import import_release_sample
from btx_omni.persistence.import_reference_fields import import_reference_fields
from btx_omni.persistence.market_series import MarketSeriesRepository


def prepare(settings: Settings) -> dict:
    root = Path(__file__).resolve().parents[2]
    origin = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=root, text=True).strip()
    if origin not in {'https://github.com/kas1172-dotcom/btx-omni-prospect.git', 'https://github.com/kas1172-dotcom/btx-omni-prospect', 'git@github.com:kas1172-dotcom/btx-omni-prospect.git'}:
        raise ValueError('E2E fixture setup requires the exact Omni Prospect repository.')
    url = make_url(settings.database_url)
    if url.host not in {'127.0.0.1', 'localhost'} or not url.database or not url.database.startswith('btx_omni_e2e'):
        raise ValueError('E2E setup requires an explicit task-owned local database named btx_omni_e2e*.')
    if settings.environment != 'development' or settings.data_mode != 'SAMPLE':
        raise ValueError('E2E fixtures require development SAMPLE mode.')
    dry = import_release_sample(settings, expected_host=url.host, expected_database=url.database)
    applied = import_release_sample(settings, apply=True, expected_host=url.host, expected_database=url.database,
                                    expected_revision=dry['prior_revision'])
    replay = import_release_sample(settings, apply=True, expected_host=url.host, expected_database=url.database,
                                   expected_revision=applied['current_revision'])
    if replay['created'] or replay['updated'] or replay['removed']:
        raise ValueError('E2E commercial replay failed.')
    references_dry = import_reference_fields(settings, expected_host=url.host, expected_database=url.database)
    references = import_reference_fields(settings, expected_host=url.host, expected_database=url.database,
        apply=True, expected_revision=references_dry['prior_revision'])
    references_replay = import_reference_fields(settings, expected_host=url.host, expected_database=url.database,
        apply=True, expected_revision=references['current_revision'])
    if references_replay['created'] or references_replay['updated'] or references_replay['removed']:
        raise ValueError('E2E original reference replay failed.')
    raw = (Path(__file__).parent / 'fixtures/g17-ip-sa-20260908.txt').read_bytes()
    if sha256(raw).hexdigest() != 'e8f510e4ade5b3d0d2c43a1339185494c0996f4b2678ca810579caf9869791c3':
        raise ValueError('Historical market test excerpt checksum changed.')
    parsed = parse_g17(raw, as_of=date(2026, 9, 8))
    engine = create_engine(settings.database_url)
    try:
        market = MarketSeriesRepository(engine).store(parsed, retrieved_at=datetime.now(UTC), source_url=G17_URL,
                                                       retrieval_kind='CI_HISTORICAL_PUBLIC_EXCERPT')
    finally:
        engine.dispose()
    return {'scope': 'DETERMINISTIC_E2E_FIXTURES_NOT_LIVE_MAPS_GEMINI_OR_MONITOR',
            'commercial': {'created': applied['created'], 'updated': applied['updated'], 'unchanged': applied['unchanged'],
                           'revision': applied['current_revision'], 'input_sha256': applied['input_sha256'],
                           'replay_created': replay['created'], 'replay_updated': replay['updated']},
            'references': references, 'market': market, 'database_version': applied['database_version']}


if __name__ == '__main__':
    print(json.dumps(prepare(Settings()), sort_keys=True))
