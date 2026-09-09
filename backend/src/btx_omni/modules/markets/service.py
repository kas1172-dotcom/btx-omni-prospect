"""Shared deterministic market read/refresh; network work happens outside SQL."""
from datetime import UTC, datetime
from time import monotonic

from btx_omni.modules.markets.g17 import parse_g17, transform
from btx_omni.modules.markets.registry import BY_ID, G17_URL, REGISTRY_VERSION, coverage
from btx_omni.providers.research.deadline import (
    PublicReadDeadlineExceeded,
    bounded_public_read,
)
from btx_omni.providers.research.http import PublicFetchError, public_request


class MarketService:
    def __init__(self, repository, *, worker_enabled=False, scheduler_configured=False):
        self.repository = repository
        self.worker_enabled = worker_enabled
        self.scheduler_configured = scheduler_configured

    def health(self):
        result = self.repository.health()
        result['schedule_status'] = ('EXTERNAL_SCHEDULER_DECLARED_NOT_EXECUTION_PROOF' if self.scheduler_configured
                                     else 'WORKER_ENABLED_SCHEDULER_UNVERIFIED') if self.worker_enabled else 'NOT_YET_CONFIGURED'
        result['refresh_policy'] = {'version': 'BTX_G17_REFRESH_1', 'success_poll_hours': 24, 'failure_retry_hours': 1,
                                    'reason': 'Monthly publication with possible revisions; one daily check, bounded hourly retry after failure.'}
        return result

    def worker_refresh(self, *, deadline_monotonic, now=None, fetch=public_request):
        if not self.worker_enabled:
            return {'status': 'DISABLED'}
        clock = now or (lambda: datetime.now(UTC))
        last_run = self.repository.health()['last_run']
        if last_run:
            last_time = datetime.fromisoformat(last_run.get('retrieved_at') or last_run['completed_at'])
            retry_seconds = 3600 if last_run['status'] == 'FAILED' else 86400
            if (clock() - last_time).total_seconds() < retry_seconds:
                return {'status': 'NOT_DUE', 'last_run_id': last_run['id'], 'retry_interval_seconds': retry_seconds}
        if deadline_monotonic - monotonic() < 20:
            return {'status': 'SKIPPED_DEADLINE', 'required_start_budget_seconds': 20}
        return self.refresh(fetch=fetch, now=clock, deadline_monotonic=deadline_monotonic)

    def refresh(self, *, fetch=public_request, now=None, deadline_monotonic=None) -> dict:
        clock = now or (lambda: datetime.now(UTC))
        try:
            deadline = min(deadline_monotonic, monotonic() + 20) if deadline_monotonic is not None else monotonic() + 20
            response = bounded_public_read(lambda: fetch(G17_URL, timeout=20, max_bytes=5_000_000), deadline)
            if response.status != 200 or not response.headers.get('content-type', '').startswith('text/'):
                raise PublicFetchError('SOURCE_UNAVAILABLE')
        except PublicReadDeadlineExceeded:
            return self.repository.failed(completed_at=clock(), reason='REFRESH_DEADLINE')
        except (PublicFetchError, OSError):
            return self.repository.failed(completed_at=clock(), reason='SOURCE_UNAVAILABLE')
        retrieved_at = clock()
        try:
            parsed = parse_g17(response.body, as_of=retrieved_at.date())
        except ValueError:
            return self.repository.failed(completed_at=retrieved_at, reason='SOURCE_CONTRACT_CHANGED')
        return self.repository.store(parsed, retrieved_at=retrieved_at, source_url=response.final_url,
                                     http_last_modified=response.headers.get('last-modified'), retrieval_kind='LIVE_PUBLIC_DOWNLOAD')

    def overview(self, *, kind='LEVEL', moving_average=False) -> dict:
        items = []
        for series_id, series in BY_ID.items():
            snapshot = self.repository.snapshot(series_id)
            latest = transform(snapshot['observations'], kind='LEVEL', periods=1) if snapshot else []
            items.append({'metadata': series.metadata(), 'status': 'AVAILABLE' if snapshot else 'NOT_COLLECTED',
                          'latest': latest[0] if latest else None,
                          'points': transform(snapshot['observations'], kind=kind, moving_average=moving_average) if snapshot else [],
                          'vintage_id': snapshot['vintage_id'] if snapshot else None,
                          'last_verified_at': snapshot['last_verified_at'] if snapshot else None})
        return {'registry_version': REGISTRY_VERSION, 'coverage': coverage(), 'series': items,
                'transformation': kind, 'moving_average_months': 3 if moving_average else None,
                'health': self.health(), 'score_effect': 'NONE',
                'authority': 'PUBLIC_MACRO_CONTEXT_NOT_CUSTOMER_ORDERS_OR_CAPACITY'}

    def detail(self, series_id: str, *, kind='LEVEL', moving_average=False, vintage_id=None) -> dict | None:
        snapshot = self.repository.snapshot(series_id, vintage_id=vintage_id)
        if snapshot is None:
            return None
        values = transform(snapshot['observations'], kind=kind, moving_average=moving_average)
        return {**snapshot, 'transformation': kind, 'moving_average_months': 3 if moving_average else None,
                'display_unit': 'INDEX_2017_100' if kind == 'LEVEL' else 'PERCENT_CHANGE',
                'points': values, 'visible_months': 36, 'vintages': self.repository.vintages(series_id),
                'regional_status': 'UNAVAILABLE_FOR_THIS_METRIC', 'source_health': self.health(),
                'interpretation': 'Macro context, not evidence that a particular customer will order more.'}
