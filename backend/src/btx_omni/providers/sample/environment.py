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
from btx_omni.domain.quotes import CommercialQuote, PaperlessAccount, QuoteStatus
from btx_omni.domain.scores import ExternalIndustryRank
from btx_omni.modules.intelligence.signals import RawSignal, SignalKind
from btx_omni.modules.matching.commercial import (
    CommercialComponent,
    HistoricalQuoteContext,
)
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.providers.research.ingestion import (
    ResearchAccount,
    apply_research_overlay,
)

ROLE_FAMILIES = ("procurement", "supply_chain", "supplier_management", "engineering", "manufacturing", "operations")

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
    paperless_accounts: tuple[PaperlessAccount, ...]
    quotes: tuple[CommercialQuote, ...]
    identity_map: dict[str, str]
    scenario_accounts: dict[str, tuple[str, ...]]
    crm_contexts: tuple[SampleCrmContext, ...]
    public_signals: tuple[SamplePublicSignal, ...]
    scoring_inputs: dict[str, dict[str, str]]
    intelligence_events: tuple[RawSignal, ...]
    matching_components: tuple[CommercialComponent, ...]
    matching_quotes: tuple[HistoricalQuoteContext, ...]
    research_mappings: dict[str, str]
    researched_accounts: tuple[ResearchAccount, ...]
    watch_profiles: tuple[AccountWatchProfile, ...]


@dataclass(frozen=True)
class SampleCrmContext:
    account_id: str
    company_id: str
    owner_id: str
    contact_role_families: tuple[str, ...]
    deal_ids: tuple[str, ...]
    activity_ids: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True)
class SamplePublicSignal:
    id: str
    account_id: str
    source_url: str
    vertical: str
    provenance: Provenance


def build_sample_environment() -> SampleEnvironment:
    deep_names = {
        "acct-01-001": "Apex Southwest Customer", "acct-01-002": "Aerospace One", "acct-01-003": "Dormant Precision", "acct-01-004": "Quote Risk Manufacturing", "acct-01-005": "Shared BU Systems", "acct-01-006": "External Top Target", "acct-01-007": "Internal Core Customer", "acct-01-008": "Conflicted Evidence Labs",
        "acct-02-001": "Defense Prime One", "acct-02-002": "Defense Two", "acct-03-001": "Phoenix Space Target", "acct-04-001": "Mesa Semiconductor Target", "acct-04-002": "Silicon Expansion Co", "acct-05-001": "MedCore Devices", "acct-05-002": "Medical Two", "acct-06-001": "Tempe Robotics Target", "acct-06-002": "Robotics Two",
    }
    accounts: list[CanonicalAccount] = []
    facilities: list[AccountFacility] = []
    ranks: list[ExternalIndustryRank] = []
    identity: dict[str, str] = {}
    for industry_index, industry in enumerate(INDUSTRIES):
        for rank in range(1, 101):
            account_id = f"acct-{industry_index + 1:02d}-{rank:03d}"
            name = deep_names.get(account_id, f"{industry} Market Target {rank:03d}")
            relationship = AccountRelationship.CURRENT_CUSTOMER if account_id in {"acct-01-001", "acct-01-003", "acct-01-004", "acct-01-005", "acct-01-007", "acct-05-001"} else AccountRelationship.TARGET
            if account_id == "acct-06-002":
                relationship = AccountRelationship.FORMER_CUSTOMER
            accounts.append(CanonicalAccount(account_id, name, relationship, f"{account_id}.sample.invalid", (industry,), ("Southwest",) if account_id in {"acct-01-001", "acct-04-001", "acct-03-001", "acct-06-001", "acct-01-005"} else (), None, ROLE_FAMILIES, _provenance(account_id)))
            facilities.append(AccountFacility(f"fac-{account_id}", account_id, f"{name} site", "Phoenix", "AZ", Decimal("33.4484") + Decimal(rank) / 10000, Decimal("-112.0740") + Decimal(rank) / 10000))
            ranks.append(ExternalIndustryRank(account_id, industry, rank, "SAMPLE Top-100 methodology", "Synthetic deterministic market-universe rank; never an attractiveness input."))
            identity.update({f"prism:{account_id}": account_id, f"paperless:{account_id}": account_id, f"hubspot:{account_id}": account_id, f"public:{name.lower()}": account_id})
    accounts, research_mappings, researched_accounts = apply_research_overlay(tuple(accounts))
    by_id = {account.id: account for account in accounts}
    deep_accounts = tuple(by_id[account_id] for account_id in deep_names)
    contexts = []
    for account in deep_accounts:
        last_booking = date(2025, 11, 1) if account.relationship is AccountRelationship.CURRENT_CUSTOMER else None
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
        contexts.append(CommercialContext(account.id, "Southwest", "USD", 1_000_000 if active else None, 900_000 if active else None, "SAMPLE", account.industries[0], "Defense Platform" if account.legal_name == "Defense Prime One" else None, "DP-100" if account.legal_name == "Defense Prime One" else None, last_booking, date(2025, 10, 1) if active else None, history, _provenance(account.id), crm, intelligence, ("POC synthetic assumption / pending PRISM confirmation: monthly revenue and bookings history", "POC synthetic assumption / pending PRISM confirmation: program, part, and last order fields")))
    # The same canonical account is intentionally represented in two BUs.
    shared = next(item for item in contexts if item.account_id == "acct-01-005")
    contexts.append(CommercialContext(shared.account_id, "Defense", shared.currency, shared.ttm_revenue_minor, shared.ttm_bookings_minor, shared.customer_segment, shared.end_market, None, None, shared.last_booking_date, shared.last_order_date, shared.monthly_history, shared.provenance, shared.last_crm_activity_date, (), shared.jamie_validation_required))
    paperless_accounts = tuple(PaperlessAccount(f"paperless-{account.id}", account.id, account.legal_name, _provenance(f"paperless-{account.id}")) for account in deep_accounts)
    quotes: list[CommercialQuote] = []
    for account in deep_accounts:
        if account.id == "acct-06-002":
            continue
        status = QuoteStatus.OPEN if account.id in {"acct-01-002", "acct-01-004", "acct-01-005", "acct-02-001", "acct-03-001"} else QuoteStatus.WON
        if account.id == "acct-02-002":
            status = QuoteStatus.LOST
        quoted_at = date(2025, 12, 25) if account.id == "acct-01-002" else date(2025, 8, 1)
        value = 250_000 if account.id in {"acct-01-004", "acct-02-001", "acct-03-001"} else 50_000
        quotes.append(CommercialQuote(f"quote-{account.id}", account.id, "Southwest", status, quoted_at, value, "USD", f"contact-{account.id}", f"fac-{account.id}", "precision-machined", _provenance(f"quote-{account.id}"), ("award-defense-1",) if account.id == "acct-02-001" else ()))
    quotes.append(CommercialQuote("quote-acct-01-005-defense", "acct-01-005", "Defense", QuoteStatus.OPEN, date(2025, 12, 20), 75_000, "USD", "contact-acct-01-005", "fac-acct-01-005", "precision-machined", _provenance("quote-acct-01-005-defense")))
    quotes.append(CommercialQuote("quote-acct-02-001-won", "acct-02-001", "Southwest", QuoteStatus.WON, date(2025, 10, 1), 300_000, "USD", "contact-acct-02-001", "fac-acct-02-001", "precision-machined", _provenance("quote-acct-02-001-won"), ("award-defense-1",)))
    crm_contexts = tuple(SampleCrmContext(account.id, f"company-{account.id}", f"owner-{account.id}", ROLE_FAMILIES, (f"deal-{account.id}",), (f"activity-{account.id}",), _provenance(f"crm-{account.id}")) for account in deep_accounts)
    public_signals = tuple(SamplePublicSignal(f"signal-{account.id}", account.id, f"https://sample.invalid/signals/{account.id}", account.industries[0], _provenance(f"public-{account.id}")) for account in deep_accounts)
    scoring_inputs = {account.id: {"program_durability.expected_production_horizon": "FIVE_TO_NINE_YEARS", "strategic_target_fit": "STRONG_TARGET_ARCHETYPE", "btx_commercial_adjacency": "EXISTING_ONE_BU_ACTIVE" if account.relationship is AccountRelationship.CURRENT_CUSTOMER else "COLD_PROSPECT"} for account in deep_accounts}
    scenario_accounts = {
        "southwest-trip": ("acct-01-001", "acct-04-001", "acct-03-001", "acct-06-001"), "medical-whitespace": ("acct-05-001", "acct-05-002"), "defense-award-quote": ("acct-02-001",), "semiconductor-expansion": ("acct-04-002",), "dormant-customer": ("acct-01-003",), "quote-follow-up": ("acct-01-004",), "cross-bu-conflict": ("acct-01-005",), "strong-external-weak-internal": ("acct-01-006",), "strong-internal-weak-external": ("acct-01-007",), "missing-conflicting-evidence": ("acct-01-008",), "bookings-decline": ("acct-02-001",), "crm-inactivity": ("acct-04-002",), "intelligence-commercial-context": ("acct-04-002",),
    }
    stamp = datetime(2025, 12, 15, tzinfo=UTC)
    intelligence_events = (
        RawSignal("award-defense-1", SignalKind.AWARD_CONTRACT, "Defense production award", "https://sample.invalid/award-defense", stamp, "Defense Prime One", "Defense Platform", EvidenceState.CONFIRMED, "Award confirms program activity."),
        RawSignal("expansion-semi-1", SignalKind.EXPANSION, "Semiconductor capacity expansion", "https://sample.invalid/expansion-semi", stamp, "Silicon Expansion Co", None, EvidenceState.CONFIRMED, "Expansion announcement."),
        RawSignal("press-ext-1", SignalKind.PRESS_RELEASE, "External target press release", "https://sample.invalid/press", stamp, "External Top Target", None, EvidenceState.INFERRED, "No internal commercial history."),
        RawSignal("financial-int-1", SignalKind.FINANCIAL_REPORT, "Internal customer financial report", "https://sample.invalid/financial", stamp, "Internal Core Customer", None, EvidenceState.CONFIRMED, "Existing commercial context remains separate."),
        RawSignal("industry-conflict-1", SignalKind.INDUSTRY_UPDATE, "Conflicting industry update", "https://sample.invalid/industry", stamp, "Conflicted Evidence Labs", None, EvidenceState.CONFLICTING, "Requires human review."),
    )
    defense_quote = next(quote for quote in quotes if quote.id == "quote-acct-02-001")
    matching_components = (
        CommercialComponent("component-defense-exact", "acct-02-001", "program-defense", "DP-100", "enclosure", "Aluminum", "5-axis", "precision-machined", EvidenceState.CONFIRMED, ("evidence-defense-component",), _provenance("component-defense"), ("precision-machining",)),
        CommercialComponent("component-defense-structured", "acct-02-001", "program-defense", None, "enclosure", "Aluminum", "5-axis", "precision-machined", EvidenceState.INFERRED, ("evidence-defense-structured",), _provenance("component-structured"), ("precision-machining",)),
        CommercialComponent("component-conflict", "acct-01-008", None, "CONFLICT-1", "bracket", "Titanium", "turning", None, EvidenceState.CONFLICTING, ("evidence-conflict",), _provenance("component-conflict")),
        CommercialComponent("component-missing", "acct-01-008", None, None, None, None, None, None, EvidenceState.MISSING, ("evidence-missing",), _provenance("component-missing")),
    )
    matching_quotes = (
        HistoricalQuoteContext(defense_quote.id, defense_quote.account_id, defense_quote.business_unit, "DP-100", "enclosure", "Aluminum", "5-axis", defense_quote.part_family, (defense_quote.provenance.source_record_id,), defense_quote.provenance),
        HistoricalQuoteContext("quote-conflict", "acct-01-008", "Southwest", "OTHER-1", "bracket", "Aluminum", "turning", None, ("quote-conflict-evidence",), _provenance("quote-conflict")),
    )
    watch_profiles = tuple(AccountWatchProfile(account.id, account.legal_name, aliases=tuple(field.value for field in account.public_identity.aliases) if account.public_identity else (), domain=account.domain, industries=account.industries) for account in accounts if account.research_account_id)
    return SampleEnvironment(tuple(accounts), tuple(facilities), tuple(ranks), tuple(contexts), paperless_accounts, tuple(quotes), identity, scenario_accounts, crm_contexts, public_signals, scoring_inputs, intelligence_events, matching_components, matching_quotes, research_mappings, researched_accounts, watch_profiles)
