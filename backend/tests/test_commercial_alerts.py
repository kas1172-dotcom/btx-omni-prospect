from datetime import UTC, datetime

from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_sample_scenarios_fire_deterministic_commercial_alerts_with_evidence() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW, orders=sample.orders)
    kinds = {alert.type for alert in alerts}
    assert {CommercialAlertKind.BOOKINGS_DECLINE, CommercialAlertKind.STALE_QUOTE, CommercialAlertKind.QUOTE_FOLLOW_UP, CommercialAlertKind.CROSS_BU_COORDINATION, CommercialAlertKind.OVERDUE_ORDER} <= kinds
    assert all(alert.evidence_ids and alert.synthetic for alert in alerts)
    assert all(alert.account_id and alert.severity and alert.trigger_reason and alert.actual_value is not None and alert.threshold is not None and alert.observed_at == NOW and alert.recommended_action and alert.status for alert in alerts)
    assert alerts == CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW, orders=sample.orders)


def test_no_alert_when_threshold_is_not_met() -> None:
    sample = build_sample_environment()
    context = next(item for item in sample.commercial_contexts if item.account_id == "lockheed-martin" and item.business_unit == "era-industries")
    alerts = CommercialAlertEngine().evaluate((context,), (), observed_at=NOW)
    assert alerts == ()


def test_overdue_order_contract_is_data_backed() -> None:
    sample = build_sample_environment()
    assert CommercialAlertEngine.overdue_order_available(sample.commercial_contexts[0], sample.orders) or any(CommercialAlertEngine.overdue_order_available(item, sample.orders) for item in sample.commercial_contexts)
