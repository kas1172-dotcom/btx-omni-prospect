"""Deterministic freshness, market, and seller-relevance policy for Monitor."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.monitor.ontology import EventType, ResolutionState, SellerRelevanceState

RECENT_WINDOW_DAYS = 30
HISTORICAL_WINDOW_DAYS = 180

# These are source-text routing terms, not a second market taxonomy.  Each
# output value is constrained to the shared primary-market definition.
MARKET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Commercial Aerospace": ("commercial aircraft", "civil aviation", "business aviation", "passenger aircraft", "faa"),
    "Defense": ("defense", "military", "missile", "weapon", "army", "navy", "air force", "dod"),
    "Space": ("space", "launch", "rocket", "lunar", "satellite", "nasa", "artemis"),
    "Robotics": ("robotics", "robotic system", "automation robot", "autonomous warehouse"),
    "Semiconductor": ("semiconductor", "chip", "wafer", "fab", "lithography", "packaging"),
    "Energy": ("energy", "nuclear", "fusion", "reactor", "turbine", "power grid"),
    "Medical": ("medical", "device", "surgical", "fda", "healthcare", "diagnostic"),
}

MATERIAL_EVENT_TYPES = frozenset(
    {
        EventType.CONTRACT_AWARD,
        EventType.CONTRACT_MODIFICATION,
        EventType.SOLICITATION,
        EventType.FACILITY_EXPANSION,
        EventType.CAPACITY_EXPANSION,
        EventType.NEW_FACILITY,
        EventType.PROGRAM_LAUNCH,
        EventType.PRODUCTION_RAMP,
        EventType.SUPPLIER_AWARD,
        EventType.SUPPLY_CHAIN_CHANGE,
        EventType.CAPITAL_INVESTMENT,
        EventType.M_AND_A,
        EventType.PARTNERSHIP,
        EventType.REGULATORY_APPROVAL,
        EventType.GOVERNMENT_FUNDING,
        EventType.GRANT_AWARD,
        EventType.BACKLOG_CHANGE,
        EventType.REGULATORY_CHANGE,
        EventType.FACILITY_CLOSURE,
        EventType.WORKFORCE_REDUCTION,
        EventType.FINANCIAL_DISTRESS,
        EventType.EXPORT_RESTRICTION,
        EventType.PRODUCTION_DELAY,
        EventType.EARNINGS_SIGNAL,
        EventType.CONTRACT_REDUCTION,
        EventType.PROGRAM_CANCELLATION,
    }
)
NOISE_TERMS = ("charity", "philanthropy", "scholarship", "lifestyle", "award ceremony", "esg report")


def classify_markets(text: str, *, source_markets: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return only evidenced primary markets, never a similarity-based guess."""
    value = text.casefold()
    matched = tuple(market for market, terms in MARKET_KEYWORDS.items() if any(term in value for term in terms))
    if matched:
        return matched
    canonical_source_markets = tuple(market for market in source_markets if market in PRIMARY_MARKETS)
    return canonical_source_markets if len(canonical_source_markets) == 1 else ()


def recency_state(event_date: datetime | None, *, now: datetime | None = None) -> str:
    if event_date is None:
        return "UNKNOWN"
    clock = now or datetime.now(UTC)
    age = clock - event_date
    if age < timedelta(0):
        return "FUTURE"
    if age <= timedelta(days=RECENT_WINDOW_DAYS):
        return "RECENT"
    if age <= timedelta(days=HISTORICAL_WINDOW_DAYS):
        return "HISTORICAL"
    return "STALE"


def seller_relevance(
    *,
    event_type: EventType,
    event_date: datetime | None,
    markets: tuple[str, ...],
    resolution_state: ResolutionState,
    source_text: str = "",
    now: datetime | None = None,
) -> SellerRelevanceState:
    """Keep public observations, but admit only current material facts to sellers."""
    freshness = recency_state(event_date, now=now)
    if freshness == "STALE" or event_type not in MATERIAL_EVENT_TYPES or not markets or any(term in source_text.casefold() for term in NOISE_TERMS):
        return SellerRelevanceState.REJECTED
    if resolution_state is ResolutionState.AMBIGUOUS:
        return SellerRelevanceState.AMBIGUOUS
    if resolution_state is ResolutionState.UNRESOLVED:
        return SellerRelevanceState.UNRESOLVED
    if freshness == "RECENT":
        return SellerRelevanceState.RESOLVED_ELIGIBLE
    return SellerRelevanceState.RESOLVED_NEEDS_REVIEW


def analysis_eligibility(
    published_at: datetime | None,
    *,
    collected_at: datetime,
    now: datetime | None = None,
    lifetime_days: int = 60,
) -> str:
    """Classify whether saved evidence can still be commercially analyzed.

    Publication age, collection freshness, and commercial usefulness are
    intentionally separate. This never changes the source publication date.
    """
    clock = now or datetime.now(UTC)
    if published_at is None:
        return "PUBLICATION_DATE_REQUIRED"
    if published_at > clock or collected_at > clock:
        return "INVALID_FUTURE_DATE"
    return (
        "ELIGIBLE"
        if clock - published_at <= timedelta(days=max(1, lifetime_days))
        else "EXPIRED"
    )
