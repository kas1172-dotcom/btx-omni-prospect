"""Revalidate selected external series; passive UI numbers are never evidence."""
from btx_omni.modules.markets.registry import BY_ID


def selected_market_context(service, filters, environment):
    series_id = filters.get('market_series_id')
    market = filters.get('market')
    vintage_id = filters.get('market_vintage_id')
    kind = filters.get('market_metric', 'LEVEL')
    average = filters.get('market_average', '0')
    if (series_id not in BY_ID or market not in BY_ID[series_id].markets
            or kind not in {'LEVEL', 'MOM_PERCENT', 'YOY_PERCENT'} or average not in {'0', '3'}):
        raise ValueError('Selected market scope is unavailable or incompatible.')
    result = service.detail(series_id, kind=kind, moving_average=average == '3')
    if result is None or result['vintage_id'] != vintage_id:
        raise ValueError('Selected market vintage is stale or unavailable.')
    points = result['points']
    latest = points[-1] if points else None
    metadata = result['metadata']
    # No full revenue duplicated into multiple sectors; account membership alone
    # is not a forecast, contribution allocation or production-site assertion.
    accounts = [{'account_id': account.id, 'name': account.legal_name}
                for account in environment.accounts if market in account.industries]
    unit = 'index (2017=100)' if kind == 'LEVEL' else 'percent ' + ('year-over-year' if kind == 'YOY_PERCENT' else 'month-over-month')
    value = latest['value'] if latest and latest['value'] is not None else 'unavailable'
    period = latest['period'] if latest else 'unavailable period'
    average_label = 'three-month average of the transformed values' if average == '3' else 'monthly observation'
    content = (f"{market}: {metadata['title']} was {value} {unit} for {period} ({average_label}). "
               f"This is seasonally adjusted United States national data from the Federal Reserve Board. "
               f"{metadata['limitation']} "
               "Macro changes do not prove customer orders, regional growth, available capacity or a change to BTX decision scores. "
               "Review the exposed accounts' actual RFQs, releases and qualification constraints before proposing a follow-up.")
    if result['source_health']['last_run'] and result['source_health']['last_run']['status'] == 'FAILED':
        content += ' The latest refresh failed; these are retained prior observations, not newly verified data.'
    return {'content': content, 'metadata': metadata, 'points': points, 'vintage_id': vintage_id,
            'retrieved_at': result['retrieved_at'], 'last_verified_at': result['last_verified_at'],
            'retrieval_kind': result.get('retrieval_kind'),
            'curated_public_context': list(getattr(service, 'curated_public_context', ())) if market == 'Medical' else [],
            'source_sha256': result['source_sha256'], 'release_date': result['release_date'],
            'transformation': kind, 'moving_average_months': result['moving_average_months'],
            'source_url': result['source_url'], 'exposed_accounts': accounts[:20], 'exposed_account_count': len(accounts),
            'exposed_accounts_omitted': max(0, len(accounts) - 20),
            'regional_status': 'UNAVAILABLE_FOR_THIS_METRIC', 'score_effect': 'NONE'}
