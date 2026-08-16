"""Canonical read-only CRM concepts; source adapters map their native fields here."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import require_aware


@dataclass(frozen=True)
class CrmCompany:
    id: str
    account_id: str
    owner_id: str | None
    provenance: Provenance


@dataclass(frozen=True)
class CrmContact:
    id: str
    company_id: str
    role_family: str
    provenance: Provenance


@dataclass(frozen=True)
class CrmDeal:
    id: str
    company_id: str
    business_unit: str | None
    provenance: Provenance


@dataclass(frozen=True)
class CrmActivity:
    id: str
    company_id: str
    occurred_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
