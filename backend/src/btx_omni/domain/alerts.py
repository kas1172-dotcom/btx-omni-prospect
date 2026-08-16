from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from btx_omni.domain.common import require_aware


class CommercialAlertKind(StrEnum):
    CUSTOMER_INACTIVITY = "CUSTOMER_INACTIVITY"
    BOOKINGS_DECLINE = "BOOKINGS_DECLINE"
    STALE_QUOTE = "STALE_QUOTE"
    QUOTE_FOLLOW_UP_GAP = "QUOTE_FOLLOW_UP_GAP"
    CRM_INACTIVITY = "CRM_INACTIVITY"
    CROSS_BU_CONFLICT = "CROSS_BU_CONFLICT"
    INTELLIGENCE_COMMERCIAL_CONTEXT = "INTELLIGENCE_COMMERCIAL_CONTEXT"
    OVERDUE_ORDER = "OVERDUE_ORDER"


@dataclass(frozen=True)
class CommercialAlert:
    id: str
    account_id: str
    kind: CommercialAlertKind
    summary: str
    evidence_ids: tuple[str, ...]
    detected_at: datetime
    order_data_required: bool = False

    def __post_init__(self) -> None:
        require_aware(self.detected_at, "detected_at")
        if not self.evidence_ids:
            raise ValueError("commercial alerts require evidence")
