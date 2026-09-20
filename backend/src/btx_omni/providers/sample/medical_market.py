"""Verified public aggregate snapshot, never synthetic customer demand.

Retrieved 2026-09-20 from the Federal Reserve G.17 current text, N3391,
2024-2026 rows (source lines 16761-16763). Public observations are fixed history,
not re-dated when the demo clock advances. No September observation is invented.
"""
import json
from copy import deepcopy
from hashlib import sha256

from btx_omni.modules.markets.registry import BY_ID
from btx_omni.providers.sample.enhancement import synthetic_record

SERIES_ID = 'FED_G17_IP_SA_N3391'
URL = 'https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt'
PUBLISHER = 'Board of Governors of the Federal Reserve System'
RETRIEVED = '2026-09-20T00:00:00+00:00'
VALUES = {
    2024: '101.3492 102.6200 101.2494 100.2690 97.5538 95.7585 95.7022 93.4038 94.9867 94.1387 94.3677 94.1096',
    2025: '92.5126 92.2730 93.1881 91.5424 90.8361 89.8609 92.0940 90.2711 89.9903 89.5536 90.0164 90.6579',
    2026: '91.2258 89.7214 92.3700 92.8556 93.9657 92.8951 92.9657 91.1064',
}


def snapshot():
    observations = [{'period': f'{year}-{month:02d}', 'value': value, 'status': 'OBSERVED',
        'source_line': 16761 + year - 2024, 'source_url': URL, 'publisher': PUBLISHER,
        'event_date': '2026-09-18', 'observation_period': f'{year}-{month:02d}', 'retrieval_date': '2026-09-20',
        'synthetic': False, 'data_mode': 'SAMPLE', 'scope': 'US_NATIONAL_AGGREGATE'}
        for year, values in VALUES.items() for month, value in enumerate(values.split(), 1)]
    digest = sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
    return {'metadata': BY_ID[SERIES_ID].metadata(), 'observations': observations,
        'vintage_id': digest, 'is_current': True, 'retrieved_at': RETRIEVED, 'last_verified_at': RETRIEVED,
        'release_date': '2026-09-18', 'event_date': '2026-09-18', 'retrieval_date': '2026-09-20',
        'publisher': PUBLISHER, 'source_url': URL, 'source_sha256': None, 'excerpt_sha256': digest,
        'release_date_source_url': 'https://www.federalreserve.gov/recentpostings.htm',
        'adapter_version': 'CURATED_G17_N3391_2026_09_20', 'retrieval_kind': 'CURATED_PUBLIC_SNAPSHOT',
        'seed_type': 'curated_public_snapshot', 'synthetic': False, 'data_mode': 'SAMPLE',
        'http_last_modified_not_release_date': None,
        'source_limitation': '32 selected published observations; excerpt hash is not a hash of the complete download. Not a live monitor run, customer forecast, regional estimate, or M&A recommendation.'}


class CuratedMarketReadRepository:
    """Overlay only an absent medical series; preserve persisted data and writes."""
    def __init__(self, repository):
        self.repository = repository

    def __getattr__(self, name):
        return getattr(self.repository, name)

    def snapshot(self, series_id, *, vintage_id=None):
        curated = snapshot() if series_id == SERIES_ID else None
        if curated and vintage_id == curated['vintage_id']:
            return deepcopy(curated)
        persisted = self.repository.snapshot(series_id, vintage_id=vintage_id)
        if persisted or vintage_id is not None:
            return persisted
        return curated

    def vintages(self, series_id):
        values = self.repository.vintages(series_id)
        if series_id == SERIES_ID:
            curated = snapshot()
            values.append({'vintage_id': curated['vintage_id'], 'retrieved_at': RETRIEVED})
        return values


def coverage_context(environment):
    rows = [(aid, a) for aid, a in environment.commercial_ledgers.items()
            if a.get('site_context', {}).get('medical_device')]
    return synthetic_record(market='Medical Device', account_ids=[aid for aid, _ in rows],
        invoiced_customer_ids=[aid for aid, a in rows if a['invoices']],
        prospect_ids=[aid for aid, a in rows if not a['invoices']],
        partnership_ids=[aid for aid, a in rows if a['site_context']['strategic_partnership']],
        btx_site_ids=['demo-btx-southwest'],
        region_counts={'AZ': len(rows)},
        interpretation='Fictional regional coverage, not actual BTX medical-device sales or site qualification. Public national production is separate context; it does not imply orders at these accounts.',
        public_context_series_id=SERIES_ID, recommendation_score=None)
