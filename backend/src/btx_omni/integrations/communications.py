from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from btx_omni.domain.communications import CommunicationDraft


@dataclass(frozen=True)
class DeliveryPreview:
    available: bool
    provider: str
    recipient_count: int
    message: str


class CommunicationDeliveryPort(Protocol):
    def preview(self, draft: CommunicationDraft) -> DeliveryPreview: ...

    def send(self, draft: CommunicationDraft, *, idempotency_key: str) -> str: ...


class DeliveryNotConfiguredError(RuntimeError):
    pass


class UnconfiguredDeliveryAdapter:
    """Truthful default: supports governed preview, never fabricates delivery."""

    def preview(self, draft: CommunicationDraft) -> DeliveryPreview:
        return DeliveryPreview(
            False,
            "UNCONFIGURED",
            len(draft.recipients),
            "Delivery is not configured. This communication remains a draft.",
        )

    def send(self, draft: CommunicationDraft, *, idempotency_key: str) -> str:
        raise DeliveryNotConfiguredError(
            "Communication delivery is not configured; no external message was sent."
        )
