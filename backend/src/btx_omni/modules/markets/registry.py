"""Reviewed series registry. Broad proxies do not establish customer demand."""
from dataclasses import asdict, dataclass

from btx_omni.domain.markets import PRIMARY_MARKET_ORDER

REGISTRY_VERSION = 'BTX_MARKET_SERIES_1'
G17_URL = 'https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt'
G17_METADATA_URL = 'https://www.federalreserve.gov/releases/g17/Current/ipdisk/g17sup_tab1.txt'


@dataclass(frozen=True)
class Series:
    id: str
    native_code: str
    title: str
    naics: str
    markets: tuple[str, ...]
    limitation: str
    metric: str = 'INDUSTRIAL_PRODUCTION'
    unit: str = 'INDEX'
    index_base: str = '2017=100'
    taxonomy: str = 'NAICS2022'
    frequency: str = 'MONTHLY'
    seasonal_adjustment: str = 'SEASONALLY_ADJUSTED'
    geography: str = 'US_NATIONAL_EXCLUDING_TERRITORIES'
    publisher: str = 'Board of Governors of the Federal Reserve System'
    source_url: str = G17_URL
    metadata_url: str = G17_METADATA_URL
    license: str = 'PUBLIC_DOMAIN_UNLESS_OTHERWISE_INDICATED; cite Federal Reserve Board'
    registry_version: str = REGISTRY_VERSION

    def metadata(self) -> dict:
        return asdict(self)


SERIES = (
    Series('FED_G17_IP_SA_G3364', 'G3364', 'Aerospace product and parts', '3364',
           ('Commercial Aerospace', 'Defense', 'Space'),
           'One shared aerospace proxy includes civil, military and space products; not separate market totals or all defense.'),
    Series('FED_G17_IP_SA_G3344', 'G3344', 'Semiconductor and other electronic component', '3344',
           ('Semiconductor',), 'Includes other electronic components; not semiconductor-equipment orders.'),
    Series('FED_G17_IP_SA_N3391', 'N3391', 'Medical equipment and supplies', '3391',
           ('Medical',), 'Manufactured equipment and supplies, not medical services or an individual customer order.'),
    Series('FED_G17_IP_SA_G3353', 'G3353', 'Electrical equipment', '3353',
           ('Energy',), 'Electrical-equipment manufacturing subset; not energy output or the entire energy supply chain.'),
)
BY_ID = {series.id: series for series in SERIES}
BY_CODE = {series.native_code: series for series in SERIES}


def coverage() -> list[dict]:
    return [{
        'market': market,
        'series_ids': [series.id for series in SERIES if market in series.markets],
        'status': 'BROAD_PROXY' if any(market in series.markets for series in SERIES) else 'UNAVAILABLE',
        'regional_status': 'UNAVAILABLE_FOR_THIS_METRIC',
        'aggregation': 'NON_ADDITIVE_SHARED_SERIES_AND_ACCOUNT_EXPOSURE',
        'missing_reason': None if market != 'Robotics' else 'No sufficiently specific production series verified.',
    } for market in PRIMARY_MARKET_ORDER]
