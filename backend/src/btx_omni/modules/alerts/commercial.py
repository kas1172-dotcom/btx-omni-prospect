"""Deterministic POC commercial alert evaluation."""
from __future__ import annotations

from datetime import datetime

from btx_omni.domain.alerts import CommercialAlert, CommercialAlertKind
from btx_omni.domain.commercial import CommercialContext
from btx_omni.domain.orders import Order
from btx_omni.domain.quotes import CommercialQuote, QuoteStatus


class CommercialAlertEngine:
    inactivity_days = 90
    crm_inactivity_days = 30
    stale_quote_days = 60
    follow_up_days = 14
    high_value_quote_minor = 100_000
    bookings_decline_ratio = 0.25

    def evaluate(self, contexts: tuple[CommercialContext, ...], quotes: tuple[CommercialQuote, ...], *, observed_at: datetime, orders: tuple[Order, ...] = ()) -> tuple[CommercialAlert, ...]:
        today = observed_at.date()
        alerts: list[CommercialAlert] = []
        for context in contexts:
            evidence = (context.provenance.source_record_id,)
            def emit(
                kind: CommercialAlertKind,
                reason: str,
                actual: object,
                threshold: object,
                action: str,
                severity: str = "MEDIUM",
                extra: tuple[str, ...] = (),
                subject_id: str | None = None,
                item: CommercialContext = context,
                item_evidence: tuple[str, ...] = evidence,
            ) -> None:
                alerts.append(
                    CommercialAlert(
                        f"alert-{kind.value.lower()}-{item.account_id}-{item.business_unit}" + (f'-{subject_id}' if subject_id else ''),
                        item.account_id,
                        kind,
                        item.business_unit,
                        severity,
                        reason,
                        actual,
                        threshold,
                        item_evidence + extra,
                        observed_at,
                        action,
                        synthetic=item.provenance.synthetic,
                        provenance_state=item.provenance.evidence_state.value,
                        subject_id=subject_id,
                    )
                )
            if context.last_booking_date and (today - context.last_booking_date).days >= self.inactivity_days:
                emit(CommercialAlertKind.CUSTOMER_INACTIVITY, "No booking within inactivity window", (today - context.last_booking_date).days, self.inactivity_days, "Confirm account status and schedule customer outreach.", "HIGH")
            history = sorted(context.monthly_history, key=lambda item: item.month)
            if len(history) >= 2 and history[-1].bookings_minor is not None and history[-2].bookings_minor not in (None, 0):
                ratio = 1 - (history[-1].bookings_minor / history[-2].bookings_minor)
                if ratio >= self.bookings_decline_ratio:
                    emit(CommercialAlertKind.BOOKINGS_DECLINE, "Bookings declined versus prior period", ratio, self.bookings_decline_ratio, "Review lost demand and recovery plan.", "HIGH")
            if context.last_crm_activity_date and (today - context.last_crm_activity_date).days >= self.crm_inactivity_days:
                emit(CommercialAlertKind.CRM_INACTIVITY, "No CRM activity within follow-up window", (today - context.last_crm_activity_date).days, self.crm_inactivity_days, "Log an account touchpoint and assign an owner.")
            if context.intelligence_evidence_ids and context.ttm_bookings_minor is not None:
                emit(CommercialAlertKind.INTELLIGENCE_COMMERCIAL_CONTEXT, "External intelligence needs commercial review", context.ttm_bookings_minor, "commercial context present", "Review intelligence against current commercial plan.", extra=context.intelligence_evidence_ids)
            for quote in quotes:
                if (quote.account_id != context.account_id or quote.status is not QuoteStatus.OPEN
                        or context.business_unit not in (quote.business_unit_ids or (quote.business_unit,))):
                    continue
                age = (today - quote.quoted_at).days
                quote_evidence = (quote.provenance.source_record_id,) + quote.quote_to_book_evidence_ids
                if quote.value_minor is not None and quote.value_minor >= self.high_value_quote_minor and age >= self.stale_quote_days:
                    emit(CommercialAlertKind.STALE_QUOTE, "Open high-value quote is stale", age, self.stale_quote_days, "Escalate quote disposition with the account owner.", "HIGH", quote_evidence, subject_id=quote.id)
                elif age >= self.follow_up_days:
                    emit(CommercialAlertKind.QUOTE_FOLLOW_UP, "Open quote requires follow-up", age, self.follow_up_days, "Contact the quote recipient and record outcome.", extra=quote_evidence, subject_id=quote.id)
        # An account represented by multiple business units requires coordination.
        by_account: dict[str, list[CommercialContext]] = {}
        for context in contexts:
            by_account.setdefault(context.account_id, []).append(context)
        for account_id, items in by_account.items():
            if len({item.business_unit for item in items}) > 1:
                evidence = tuple(item.provenance.source_record_id for item in items)
                alerts.append(CommercialAlert(f"alert-cross_bu_coordination-{account_id}", account_id, CommercialAlertKind.CROSS_BU_COORDINATION, None, "MEDIUM", "Multiple business units have active commercial context", tuple(sorted(item.business_unit for item in items)), 1, evidence, observed_at, "Coordinate account strategy across business units.", synthetic=all(item.provenance.synthetic for item in items), provenance_state="CONFIRMED"))
        for order in orders:
            if order.promised_date and order.actual_ship_date is None and order.promised_date < today and order.status not in {"CANCELLED", "SHIPPED"}:
                alerts.append(CommercialAlert(f"alert-overdue_order-{order.id}", order.account_id, CommercialAlertKind.OVERDUE_ORDER, order.business_unit_id, "HIGH", "Order is past its promised ship date", (today - order.promised_date).days, 0, (order.provenance.source_record_id,), observed_at, "Confirm fulfillment status and customer recovery plan.", synthetic=order.provenance.synthetic, provenance_state=order.provenance.evidence_state.value))
        return tuple(sorted(alerts, key=lambda item: item.id))

    @staticmethod
    def overdue_order_available(context: CommercialContext, orders: tuple[Order, ...] = ()) -> bool:
        return any(order.account_id == context.account_id and order.business_unit_id == context.business_unit and order.promised_date is not None for order in orders)
