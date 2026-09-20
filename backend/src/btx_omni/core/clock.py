"""One reproducible business clock; authentication/timeout clocks are separate."""
from datetime import UTC, date, datetime, time, timedelta

from btx_omni.core.config import get_settings


def as_of_datetime(value: str | date | datetime | None = None) -> datetime:
    value = value if value is not None else get_settings().demo_as_of_date
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return datetime.combine(value, time.min, UTC)


def as_of_date(value: str | date | datetime | None = None) -> date:
    return as_of_datetime(value).date()


def relative_date(days: int = 0, *, anchor=None) -> str:
    return (as_of_date(anchor) + timedelta(days=days)).isoformat()


def evidence_state(observed_at, *, as_of=None, window_days: int = 2) -> str:
    """Inclusive expiry; absent, invalid and future timestamps are unknown."""
    try:
        age = as_of_datetime(as_of) - as_of_datetime(observed_at) if observed_at else None
    except (ValueError, TypeError):
        return 'UNKNOWN'
    if age is None or age < timedelta(0):
        return 'UNKNOWN'
    return 'CURRENT' if age <= timedelta(days=window_days) else 'STALE'
