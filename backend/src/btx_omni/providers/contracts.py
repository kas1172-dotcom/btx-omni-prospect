"""Typed read contracts shared by SAMPLE and CONNECTED providers."""
from __future__ import annotations

from typing import Protocol

from btx_omni.domain.accounts import CanonicalAccount
from btx_omni.domain.commercial import CommercialContext
from btx_omni.domain.quotes import CommercialQuote


class AccountProvider(Protocol):
    def accounts(self) -> tuple[CanonicalAccount, ...]: ...


class CommercialContextProvider(Protocol):
    def commercial_context(self, account_id: str) -> tuple[CommercialContext, ...]: ...


class QuoteProvider(Protocol):
    def quotes(self, account_id: str) -> tuple[CommercialQuote, ...]: ...
