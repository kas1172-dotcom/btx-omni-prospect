from datetime import UTC, datetime

from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_sample_scenarios_fire_deterministic_commercial_alerts_with_evidence() -> None:
    sample = build_sample_environment()
    alerts = CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW)
    kinds = {alert.type for alert in alerts}
    assert {CommercialAlertKind.CUSTOMER_INACTIVITY, CommercialAlertKind.BOOKINGS_DECLINE, CommercialAlertKind.STALE_QUOTE, CommercialAlertKind.QUOTE_FOLLOW_UP, CommercialAlertKind.CRM_INACTIVITY, CommercialAlertKind.CROSS_BU_COORDINATION, CommercialAlertKind.INTELLIGENCE_COMMERCIAL_CONTEXT} <= kinds
    assert all(alert.evidence_ids and alert.synthetic for alert in alerts)
    assert alerts == CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW)


def test_no_alert_when_threshold_is_not_met() -> None:
    sample = build_sample_environment()
    context = next(item for item in sample.commercial_contexts if item.account_id == sample.accounts[0].id)
    alerts = CommercialAlertEngine().evaluate((context,), (), observed_at=NOW)
    assert alerts == ()


def test_overdue_order_contract_remains_unavailable_without_required_fields() -> None:
    sample = build_sample_environment()
    assert not CommercialAlertEngine.overdue_order_available(sample.commercial_contexts[0])
