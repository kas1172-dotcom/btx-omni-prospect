"""Provider-neutral durable collection state for procurement sources."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CoverageState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    RATE_LIMITED = "RATE_LIMITED"
    FAILED = "FAILED"
    AWAITING_CONTINUATION = "AWAITING_CONTINUATION"


@dataclass(frozen=True)
class ProcurementCheckpoint:
    source_id: str
    query_key: str
    query_value: str
    window_start: datetime
    window_end: datetime
    offset: int = 0
    page_size: int = 100
    total_records: int | None = None
    coverage_state: CoverageState = CoverageState.AWAITING_CONTINUATION
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_complete_at: datetime | None = None
    next_retry_at: datetime | None = None
    source_modified_at: datetime | None = None
    records_collected: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    records_rejected: int = 0
    failure_count: int = 0
    last_error: str | None = None

    @property
    def pending(self) -> bool:
        return self.coverage_state is not CoverageState.COMPLETE


@dataclass(frozen=True)
class ProcurementCollectionResult:
    observations: tuple
    checkpoints: tuple[ProcurementCheckpoint, ...]
    warnings: tuple[str, ...] = ()


def initial_checkpoint(
    *, source_id: str, query_key: str, query_value: str, now: datetime,
    lookback_days: int, page_size: int,
) -> ProcurementCheckpoint:
    return ProcurementCheckpoint(
        source_id=source_id,
        query_key=query_key,
        query_value=query_value,
        window_start=now - timedelta(days=lookback_days),
        window_end=now,
        page_size=page_size,
    )


def next_incremental_window(
    checkpoint: ProcurementCheckpoint, *, now: datetime, overlap_days: int
) -> ProcurementCheckpoint:
    """Start a new overlapping window only after the previous one is complete."""
    if checkpoint.coverage_state is not CoverageState.COMPLETE:
        return checkpoint
    start = checkpoint.window_end - timedelta(days=overlap_days)
    if start > now:
        start = now - timedelta(days=overlap_days)
    return replace(
        checkpoint,
        window_start=start,
        window_end=now,
        offset=0,
        total_records=None,
        coverage_state=CoverageState.AWAITING_CONTINUATION,
        records_collected=0,
        records_created=0,
        records_updated=0,
        records_unchanged=0,
        records_rejected=0,
        last_error=None,
        next_retry_at=None,
    )


def retry_at(now: datetime, failure_count: int) -> datetime:
    return now + timedelta(seconds=min(3600, 30 * (2 ** min(failure_count, 7))))


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
