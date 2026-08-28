"""BTX canonical industry taxonomy and source-boundary normalization."""
from __future__ import annotations

from enum import StrEnum


class CanonicalMarket(StrEnum):
    DEFENSE = "Defense"
    COMMERCIAL_AEROSPACE = "Commercial Aerospace"
    SPACE = "Space"
    ROBOTICS = "Robotics"
    SEMICONDUCTOR = "Semiconductor"
    MEDICAL = "Medical"
    ENERGY = "Energy"


PRIMARY_MARKET_ORDER = tuple(market.value for market in CanonicalMarket)
PRIMARY_MARKETS = frozenset(PRIMARY_MARKET_ORDER)
UNCLASSIFIED_MARKET = "Unclassified"

_SOURCE_ALIASES = {
    "commercial aerospace": CanonicalMarket.COMMERCIAL_AEROSPACE.value,
    "commercial_aerospace": CanonicalMarket.COMMERCIAL_AEROSPACE.value,
    "defense": CanonicalMarket.DEFENSE.value,
    "space": CanonicalMarket.SPACE.value,
    "space exploration": CanonicalMarket.SPACE.value,
    "robotics": CanonicalMarket.ROBOTICS.value,
    "semiconductor": CanonicalMarket.SEMICONDUCTOR.value,
    "semiconductors": CanonicalMarket.SEMICONDUCTOR.value,
    "medical": CanonicalMarket.MEDICAL.value,
    "energy": CanonicalMarket.ENERGY.value,
}
AMBIGUOUS_SOURCE_MARKETS = frozenset({"aerospace"})


class AmbiguousMarketError(ValueError):
    """Raised when a source category cannot safely become a canonical market."""


def normalize_source_market(value: str) -> str:
    """Normalize an unambiguous provider value; never guess legacy Aerospace."""
    key = " ".join(value.strip().casefold().split())
    if key in AMBIGUOUS_SOURCE_MARKETS:
        raise AmbiguousMarketError(
            "legacy Aerospace requires explicit commercial/defense disambiguation"
        )
    try:
        return _SOURCE_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"unsupported source market: {value}") from error


def primary_market_label(markets: tuple[str, ...]) -> str:
    """Return a display-safe primary market without inventing a classification."""
    return markets[0] if markets else UNCLASSIFIED_MARKET
