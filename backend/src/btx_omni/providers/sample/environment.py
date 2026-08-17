"""POC runtime: real researched companies plus clearly simulated BTX context."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

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
from btx_omni.modules.intelligence.signals import RawSignal
from btx_omni.modules.matching.commercial import (
    CommercialComponent,
    HistoricalQuoteContext,
)
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.providers.research.ingestion import (
    ResearchAccount,
    apply_facility_feed_enrichment,
    build_researched_canonical_accounts,
    load_usaspending_recipient_identities,
)
from btx_omni.providers.research.scenarios import SCENARIOS as RICH_SCENARIOS
from btx_omni.providers.research.scenarios import RichScenario

ROLE_FAMILIES = ("procurement", "supply_chain", "supplier_management", "engineering", "manufacturing", "operations")
SCENARIOS = ("southwest-trip", "medical-whitespace", "defense-award-quote", "semiconductor-expansion", "dormant-customer", "quote-follow-up", "cross-bu-conflict", "needs-research", "bookings-decline", "crm-inactivity", "intelligence-commercial-context")


def _provenance(record_id: str) -> Provenance:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Provenance("poc-simulated-btx-context", record_id, None, now, now, Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED, DataMode.SAMPLE, True)


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


@dataclass(frozen=True)
class SampleEnvironment:
    accounts: tuple[CanonicalAccount, ...]
    facilities: tuple[AccountFacility, ...]
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
    public_facilities: tuple[AccountFacility, ...]
    rich_scenarios: dict[str, RichScenario]


def build_sample_environment() -> SampleEnvironment:
    """Never generate placeholder companies, locations, ranks, or public events."""
    accounts, research_mappings, researched_accounts = build_researched_canonical_accounts()
    rich_scenarios = {item.research_account_id: item for item in RICH_SCENARIOS}
    scenario_ids = set(rich_scenarios)
    customer_ids = {"boeing", "lockheed-martin", "applied-materials"}
    accounts = tuple(replace(item, relationship=AccountRelationship.PUBLIC_MARKET, business_units=("Southwest",) if item.id in customer_ids else ()) for item in accounts)
    accounts, public_facilities = apply_facility_feed_enrichment(accounts, research_mappings)
    by_id = {item.id: item for item in accounts}
    facilities = tuple(item for item in public_facilities if item.account_id in by_id)

    contexts: list[CommercialContext] = []
    for account_id in scenario_ids:
        account = by_id[account_id]
        active = account_id in customer_ids or account_id in {"ge-aerospace", "intel"}
        history = (MonthlyCommercialHistory(date(2025, 12, 1), 80_000, 75_000, _provenance(account_id)),)
        if account_id == "applied-materials":
            history = (MonthlyCommercialHistory(date(2025, 11, 1), 100_000, 200_000, _provenance(account_id)), MonthlyCommercialHistory(date(2025, 12, 1), 100_000, 100_000, _provenance(account_id)))
        contexts.append(CommercialContext(account_id, "Southwest", "USD", 1_000_000 if active else None, 900_000 if active else None, "SIMULATED_POC", account.industries[0], "Simulated program context" if account_id == "lockheed-martin" else None, "SIM-100" if account_id == "lockheed-martin" else None, date(2025, 8, 1) if account_id == "applied-materials" else (date(2025, 11, 1) if active else None), date(2025, 10, 1) if active else None, history, _provenance(account_id), date(2025, 11, 1) if account_id == "intel" else date(2025, 12, 20), ("CHIPS_INTEL",) if account_id == "intel" else (), ("POC simulation / pending BTX system confirmation: revenue, bookings, program, part, and activity fields.",)))
    contexts.append(replace(next(item for item in contexts if item.account_id == "boeing"), business_unit="Defense"))

    paperless_accounts = tuple(PaperlessAccount(f"paperless-{account_id}", account_id, by_id[account_id].legal_name, _provenance(f"paperless-{account_id}")) for account_id in scenario_ids)
    quotes: list[CommercialQuote] = []
    for account_id in scenario_ids - {"symbotic"}:
        status = QuoteStatus.OPEN if account_id in {"ge-aerospace", "intel", "boeing", "lockheed-martin", "blue-origin"} else QuoteStatus.WON
        if account_id == "anduril-industries": status = QuoteStatus.LOST
        quotes.append(CommercialQuote(f"quote-{account_id}", account_id, "Southwest", status, date(2025, 12, 25) if account_id == "ge-aerospace" else date(2025, 8, 1), 250_000 if account_id in {"lockheed-martin", "blue-origin"} else 50_000, "USD", f"sim-contact-{account_id}", None, "precision-machined", _provenance(f"quote-{account_id}"), ("DOD_LOCKHEED",) if account_id == "lockheed-martin" else ()))
    quotes.append(CommercialQuote("quote-boeing-defense", "boeing", "Defense", QuoteStatus.OPEN, date(2025, 12, 20), 75_000, "USD", "sim-contact-boeing", None, "precision-machined", _provenance("quote-boeing-defense")))
    quotes.append(CommercialQuote("quote-lockheed-won", "lockheed-martin", "Southwest", QuoteStatus.WON, date(2025, 10, 1), 300_000, "USD", "sim-contact-lockheed", None, "precision-machined", _provenance("quote-lockheed-won"), ("DOD_LOCKHEED",)))

    crm_contexts = tuple(SampleCrmContext(account_id, f"sim-company-{account_id}", f"sim-owner-{account_id}", ROLE_FAMILIES, (f"sim-deal-{account_id}",), (f"sim-activity-{account_id}",), _provenance(f"crm-{account_id}")) for account_id in scenario_ids)
    public_signals = tuple(SamplePublicSignal(scenario.event.source_id, account_id, scenario.event.source_url, by_id[account_id].industries[0], by_id[account_id].provenance) for account_id, scenario in rich_scenarios.items())
    scoring_inputs = {account_id: scenario.simulated_score_inputs for account_id, scenario in rich_scenarios.items() if scenario.simulated_score_inputs}
    scenario_accounts = {"southwest-trip": ("boeing", "tsmc-arizona", "blue-origin", "symbotic"), "medical-whitespace": ("medtronic",), "defense-award-quote": ("lockheed-martin",), "semiconductor-expansion": ("intel",), "dormant-customer": ("applied-materials",), "quote-follow-up": ("ge-aerospace",), "cross-bu-conflict": ("boeing",), "needs-research": ("rocket-lab-usa",), "bookings-decline": ("applied-materials",), "crm-inactivity": ("intel",), "intelligence-commercial-context": ("intel",)}
    lockheed_quote = next(quote for quote in quotes if quote.id == "quote-lockheed-martin")
    matching_components = (CommercialComponent("component-lockheed-exact", "lockheed-martin", "sim-program-lockheed", "SIM-100", "enclosure", "Aluminum", "5-axis", "precision-machined", EvidenceState.CONFIRMED, ("DOD_LOCKHEED",), _provenance("component-lockheed"), ("precision-machining",)), CommercialComponent("component-lockheed-structured", "lockheed-martin", "sim-program-lockheed", None, "enclosure", "Aluminum", "5-axis", "precision-machined", EvidenceState.INFERRED, ("DOD_LOCKHEED",), _provenance("component-lockheed-structured"), ("precision-machining",)))
    matching_quotes = (HistoricalQuoteContext(lockheed_quote.id, lockheed_quote.account_id, lockheed_quote.business_unit, "SIM-100", "enclosure", "Aluminum", "5-axis", lockheed_quote.part_family, (lockheed_quote.provenance.source_record_id,), lockheed_quote.provenance),)
    public_facilities_by_account: dict[str, list[str]] = {}
    for facility in public_facilities: public_facilities_by_account.setdefault(facility.account_id, []).append(facility.id)
    recipient_identities = load_usaspending_recipient_identities()
    watch_profiles = tuple(AccountWatchProfile(item.id, item.legal_name, aliases=tuple(field.value for field in item.public_identity.aliases) if item.public_identity else (), domain=item.domain, newsroom_url=item.public_identity.newsroom_url.value if item.public_identity and item.public_identity.newsroom_url else None, investor_relations_url=item.public_identity.investor_relations_url.value if item.public_identity and item.public_identity.investor_relations_url else None, official_feed_urls=tuple(field.value for field in item.public_identity.official_feed_urls) if item.public_identity else (), facilities=tuple(public_facilities_by_account.get(item.id, ())), industries=item.industries, usaspending_recipient_names=tuple(identity.recipient_legal_name for identity in recipient_identities.get(item.id, ())), usaspending_recipient_sources=tuple((identity.recipient_legal_name, identity.source_url) for identity in recipient_identities.get(item.id, ()))) for item in accounts)
    identity_map = {f"public:{item.legal_name.lower()}": item.id for item in accounts}
    return SampleEnvironment(accounts, facilities, tuple(contexts), paperless_accounts, tuple(quotes), identity_map, scenario_accounts, crm_contexts, public_signals, scoring_inputs, tuple(scenario.event for scenario in rich_scenarios.values()), matching_components, matching_quotes, research_mappings, researched_accounts, watch_profiles, public_facilities, rich_scenarios)
