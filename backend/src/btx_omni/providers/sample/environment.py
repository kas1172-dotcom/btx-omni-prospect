"""Deterministic SAMPLE runtime; no donor fixture format or data is reused."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    AccountFacility,
    AccountRelationship,
    CanonicalAccount,
)
from btx_omni.domain.commercial import CommercialContext, MonthlyCommercialHistory
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.quotes import CommercialQuote, QuoteStatus
from btx_omni.domain.scores import ExternalIndustryRank

INDUSTRIES = ("Commercial Aerospace", "Defense", "Space", "Semiconductor", "Medical Device", "Robotics")
SCENARIOS = (
    "southwest-trip", "medical-whitespace", "defense-award-quote", "semiconductor-expansion",
    "dormant-customer", "quote-follow-up", "cross-bu-conflict", "strong-external-weak-internal",
    "strong-internal-weak-external", "missing-conflicting-evidence",
)


def _provenance(record_id: str) -> Provenance:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Provenance("sample-environment", record_id, None, now, now, Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED, DataMode.SAMPLE, True)


@dataclass(frozen=True)
class SampleEnvironment:
    accounts: tuple[CanonicalAccount, ...]
    facilities: tuple[AccountFacility, ...]
    ranks: tuple[ExternalIndustryRank, ...]
    commercial_contexts: tuple[CommercialContext, ...]
    quotes: tuple[CommercialQuote, ...]
    identity_map: dict[str, str]
    scenario_accounts: dict[str, tuple[str, ...]]


def build_sample_environment() -> SampleEnvironment:
    deep_names = ("Apex Southwest Customer", "Mesa Semiconductor Target", "Phoenix Space Target", "Tempe Robotics Target", "MedCore Devices", "Defense Prime One", "Silicon Expansion Co", "Dormant Precision", "Quote Risk Manufacturing", "Shared BU Systems", "External Top Target", "Internal Core Customer", "Conflicted Evidence Labs", "Aerospace One", "Defense Two", "Medical Two", "Robotics Two")
    accounts: list[CanonicalAccount] = []
    facilities: list[AccountFacility] = []
    ranks: list[ExternalIndustryRank] = []
    identity: dict[str, str] = {}
    for industry_index, industry in enumerate(INDUSTRIES):
        for rank in range(1, 101):
            deep = industry_index == 0 and rank <= len(deep_names)
            account_id = f"acct-{industry_index + 1:02d}-{rank:03d}"
            name = deep_names[rank - 1] if deep else f"{industry} Market Target {rank:03d}"
            relationship = AccountRelationship.CURRENT_CUSTOMER if deep and rank in {1, 5, 8, 9, 10, 12} else AccountRelationship.TARGET
            accounts.append(CanonicalAccount(account_id, name, relationship, f"{account_id}.sample.invalid", (industry,), ("Southwest",) if rank in {1, 2, 3, 4, 10} else ()))
            facilities.append(AccountFacility(f"fac-{account_id}", account_id, f"{name} site", "Phoenix", "AZ", Decimal("33.4484") + Decimal(rank) / 10000, Decimal("-112.0740") + Decimal(rank) / 10000))
            ranks.append(ExternalIndustryRank(account_id, industry, rank, "SAMPLE Top-100 methodology", "Synthetic deterministic market-universe rank; never an attractiveness input."))
            identity.update({f"prism:{account_id}": account_id, f"paperless:{account_id}": account_id, f"hubspot:{account_id}": account_id, f"public:{name.lower()}": account_id})
    contexts = tuple(CommercialContext(account_id=a.id, business_unit="Southwest", currency="USD", ttm_revenue_minor=1_000_000 if a.relationship is AccountRelationship.CURRENT_CUSTOMER else None, ttm_bookings_minor=900_000 if a.relationship is AccountRelationship.CURRENT_CUSTOMER else None, customer_segment="SAMPLE", end_market=a.industries[0], platform_program=None, part_number=None, last_booking_date=date(2025, 11, 1), last_order_date=date(2025, 10, 1), monthly_history=(MonthlyCommercialHistory(date(2025, 12, 1), 80_000, 75_000, _provenance(a.id)),), provenance=_provenance(a.id), jamie_validation_required=("monthly_history", "last_order_date")) for a in accounts[:17])
    quotes = tuple(CommercialQuote(f"quote-{a.id}", a.id, "Southwest", QuoteStatus.OPEN if index in {5, 9} else QuoteStatus.WON, date(2025, 8, 1), 250_000, "USD", None, f"fac-{a.id}", "precision-machined", _provenance(a.id)) for index, a in enumerate(accounts[:17], 1))
    scenario_accounts = {scenario: (accounts[index].id,) for index, scenario in enumerate(SCENARIOS)}
    scenario_accounts["southwest-trip"] = tuple(account.id for account in accounts[:4])
    return SampleEnvironment(tuple(accounts), tuple(facilities), tuple(ranks), contexts, quotes, identity, scenario_accounts)
