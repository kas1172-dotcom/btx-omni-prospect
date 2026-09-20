from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from btx_omni.domain.common import require_aware


class CommercialAlertKind(StrEnum):
    CUSTOMER_INACTIVITY = "CUSTOMER_INACTIVITY"
    BOOKINGS_DECLINE = "BOOKINGS_DECLINE"
    STALE_QUOTE = "STALE_QUOTE"
    QUOTE_FOLLOW_UP = "QUOTE_FOLLOW_UP"
    CRM_INACTIVITY = "CRM_INACTIVITY"
    CROSS_BU_COORDINATION = "CROSS_BU_COORDINATION"
    INTELLIGENCE_COMMERCIAL_CONTEXT = "INTELLIGENCE_COMMERCIAL_CONTEXT"
    OVERDUE_ORDER = "OVERDUE_ORDER"


@dataclass(frozen=True)
class CommercialAlert:
    id: str
    account_id: str
    type: CommercialAlertKind
    business_unit: str | None
    severity: str
    trigger_reason: str
    actual_value: Any
    threshold: Any
    evidence_ids: tuple[str, ...]
    observed_at: datetime
    recommended_action: str
    owner_id: str | None = None
    status: str = "OPEN"
    synthetic: bool = False
    provenance_state: str = "CONFIRMED"
    order_data_required: bool = False
    subject_id: str | None = None
    hard_stop: bool = False

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "observed_at")
        if not self.evidence_ids:
            raise ValueError("commercial alerts require evidence")
