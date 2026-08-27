"""Read-only CRM and governed-write seams; no live HubSpot client is wired."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

from btx_omni.domain.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal


class CrmProviderState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CrmAccountContext:
    company: CrmCompany | None
    contacts: tuple[CrmContact, ...]
    deals: tuple[CrmDeal, ...]
    activities: tuple[CrmActivity, ...]
    shared_owner_ids: tuple[str, ...]
    state: CrmProviderState
    detail: str | None = None

    @property
    def last_meaningful_contact(self) -> CrmActivity | None:
        return max(self.activities, key=lambda item: item.occurred_at, default=None)


@dataclass(frozen=True)
class CrmActionPreview:
    action_id: str
    account_id: str
    operation: str
    payload: dict[str, str]
    confirmed: bool = False
    executed: bool = False
    unavailable_reason: str | None = None


class CrmWritePort(Protocol):
    """Provider-neutral boundary for explicit, governed CRM operations."""

    def preview_action(self, action_id: str, account_id: str, operation: str, payload: dict[str, str]) -> CrmActionPreview: ...

    def execute_action(self, preview: CrmActionPreview) -> CrmActionPreview: ...


class SampleHubSpotAdapter:
    def __init__(self, contexts: dict[str, CrmAccountContext], state: CrmProviderState = CrmProviderState.AVAILABLE) -> None:
        self._contexts, self._state = contexts, state

    def account_context(self, account_id: str) -> CrmAccountContext:
        if self._state is CrmProviderState.UNAVAILABLE:
            return CrmAccountContext(None, (), (), (), (), self._state, "HubSpot provider is unavailable.")
        return self._contexts.get(account_id, CrmAccountContext(None, (), (), (), (), self._state, "No CRM company is linked to this canonical account."))

    def preview_action(self, action_id: str, account_id: str, operation: str, payload: dict[str, str]) -> CrmActionPreview:
        return CrmActionPreview(action_id, account_id, operation, dict(payload))

    def execute_action(self, preview: CrmActionPreview) -> CrmActionPreview:
        if not preview.confirmed:
            raise PermissionError("explicit human confirmation is required before CRM execution")
        if self._state is CrmProviderState.UNAVAILABLE:
            return replace(preview, unavailable_reason="HubSpot provider is unavailable.")
        # SAMPLE seam only: deterministic state transition, never an external write.
        return replace(preview, executed=True)
