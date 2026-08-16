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
    "strong-internal-weak-external", "missing-conflicting-evidence", "bookings-decline",
    "crm-inactivity", "intelligence-commercial-context",
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
    contexts = []
    for index, account in enumerate(accounts[:17], 1):
        last_booking = date(2025, 11, 1)
        history = (MonthlyCommercialHistory(date(2025, 12, 1), 80_000, 75_000, _provenance(account.id)),)
        crm = date(2025, 12, 20)
        intelligence: tuple[str, ...] = ()
        if account.legal_name == "Dormant Precision":
            last_booking = date(2025, 8, 1)
        if account.legal_name == "Defense Prime One":
            history = (MonthlyCommercialHistory(date(2025, 11, 1), 100_000, 200_000, _provenance(account.id)), MonthlyCommercialHistory(date(2025, 12, 1), 100_000, 100_000, _provenance(account.id)))
        if account.legal_name == "Silicon Expansion Co":
            crm = date(2025, 11, 1)
            intelligence = ("intel-silicon-expansion",)
        active = account.relationship is AccountRelationship.CURRENT_CUSTOMER or account.legal_name == "Silicon Expansion Co"
        contexts.append(CommercialContext(account.id, "Southwest", "USD", 1_000_000 if active else None, 900_000 if active else None, "SAMPLE", account.industries[0], None, None, last_booking, date(2025, 10, 1), history, _provenance(account.id), crm, intelligence, ("monthly_history", "last_order_date")))
    # The same canonical account is intentionally represented in two BUs.
    shared = next(item for item in contexts if item.account_id == accounts[9].id)
    contexts.append(CommercialContext(shared.account_id, "Defense", shared.currency, shared.ttm_revenue_minor, shared.ttm_bookings_minor, shared.customer_segment, shared.end_market, None, None, shared.last_booking_date, shared.last_order_date, shared.monthly_history, shared.provenance, shared.last_crm_activity_date, (), shared.jamie_validation_required))
    quotes = tuple(CommercialQuote(f"quote-{a.id}", a.id, "Southwest", QuoteStatus.OPEN if a.legal_name in {"Quote Risk Manufacturing", "Defense Prime One"} else QuoteStatus.WON, date(2025, 8, 1), 50_000 if a.legal_name == "Defense Prime One" else 250_000, "USD", None, f"fac-{a.id}", "precision-machined", _provenance(a.id)) for a in accounts[:17])
    scenario_accounts = {scenario: (accounts[index].id,) for index, scenario in enumerate(SCENARIOS)}
    scenario_accounts["southwest-trip"] = tuple(account.id for account in accounts[:4])
    scenario_accounts.update({"bookings-decline": (accounts[5].id,), "crm-inactivity": (accounts[6].id,), "intelligence-commercial-context": (accounts[6].id,)})
    return SampleEnvironment(tuple(accounts), tuple(facilities), tuple(ranks), tuple(contexts), quotes, identity, scenario_accounts)
