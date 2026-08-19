"""BTX POC primary-market taxonomy and safe display helpers."""
from __future__ import annotations

PRIMARY_MARKETS = frozenset({"Aerospace", "Defense", "Semiconductor", "Space Exploration", "Energy", "Medical"})
UNCLASSIFIED_MARKET = "Unclassified"


def primary_market_label(markets: tuple[str, ...]) -> str:
    """Return a display-safe primary market without inventing a classification."""
    return markets[0] if markets else UNCLASSIFIED_MARKET
