"""Only complete, current governed monitoring can establish a zero-risk read."""
def monitoring_complete(monitor, account_id: str) -> bool:
    relevant = [source for source, targets in monitor.watch_targets.items()
                if any(target.canonical_account_id == account_id for target in targets)]
    if not relevant:
        return False
    snapshot = monitor.durable_snapshot()
    health = {row['source_id']: row for row in (snapshot or {}).get('health', ())}
    if monitor.repository:
        coverage = monitor.repository.procurement_coverage(None)
        if any(row.get('coverage_state', row.get('status')) not in {'COMPLETE', 'complete'} for row in coverage):
            return False
    for source in relevant:
        status = monitor.operational_status(source, durable_health=health.get(source))
        if str(status.state) != 'HEALTHY' or not status.last_success_at:
            return False
    return True
