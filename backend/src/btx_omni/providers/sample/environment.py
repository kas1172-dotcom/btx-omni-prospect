"""Composition root for the fixture-backed SAMPLE provider family."""
from __future__ import annotations

from dataclasses import dataclass, replace

from btx_omni.domain.accounts import (
    AccountFacility,
    AccountRelationship,
    CanonicalAccount,
)
from btx_omni.domain.btx import BtxBusinessUnit, BtxFacility
from btx_omni.domain.capabilities import Capability
from btx_omni.domain.commercial import CommercialContext
from btx_omni.domain.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal
from btx_omni.domain.markets import primary_market_label
from btx_omni.domain.orders import Order
from btx_omni.domain.programs import ComponentClass, Program
from btx_omni.domain.quotes import CommercialQuote, PaperlessAccount
from btx_omni.domain.relationships import AccountRelationshipEdge
from btx_omni.modules.intelligence.signals import RawSignal
from btx_omni.modules.matching.commercial import (
    CommercialComponent,
    HistoricalQuoteContext,
)
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.providers.hubspot_sample.crm import load_crm
from btx_omni.providers.lake_sample.context import load_commercial_contexts
from btx_omni.providers.lake_sample.orders import load_orders
from btx_omni.providers.paperless_sample.quotes import load_paperless_quotes
from btx_omni.providers.research.btx_profile import (
    load_btx_business_units,
    load_btx_facilities,
)
from btx_omni.providers.research.capabilities import load_capabilities
from btx_omni.providers.research.components import load_component_classes
from btx_omni.providers.research.ingestion import (
    ResearchAccount,
    apply_facility_feed_enrichment,
    build_researched_canonical_accounts,
    load_usaspending_recipient_identities,
)
from btx_omni.providers.research.programs import load_programs
from btx_omni.providers.research.reference_data import load_reference_import
from btx_omni.providers.research.relationships import load_relationship_edges
from btx_omni.providers.research.scenarios import SCENARIOS as RICH_SCENARIOS
from btx_omni.providers.research.scenarios import RichScenario

ROLE_FAMILIES = ("procurement", "supply_chain", "supplier_management", "engineering", "manufacturing", "operations")
SCENARIOS = ("southwest-trip", "medical-whitespace", "defense-award-quote", "semiconductor-expansion", "dormant-customer", "quote-follow-up", "cross-bu-conflict", "strong-external-weak-internal", "strong-internal-weak-external", "missing-unresolved-conflicting")


@dataclass(frozen=True)
class PublicScenarioSignal:
    id: str
    account_id: str
    source_url: str
    vertical: str
    provenance: object


@dataclass(frozen=True)
class SampleEnvironment:
    accounts: tuple[CanonicalAccount, ...]
    facilities: tuple[AccountFacility, ...]
    commercial_contexts: tuple[CommercialContext, ...]
    paperless_accounts: tuple[PaperlessAccount, ...]
    quotes: tuple[CommercialQuote, ...]
    orders: tuple[Order, ...]
    business_units: tuple[BtxBusinessUnit, ...]
    btx_facilities: tuple[BtxFacility, ...]
    capabilities: tuple[Capability, ...]
    programs: tuple[Program, ...]
    component_classes: tuple[ComponentClass, ...]
    relationship_edges: tuple[AccountRelationshipEdge, ...]
    crm_companies: tuple[CrmCompany, ...]
    crm_contacts: tuple[CrmContact, ...]
    crm_deals: tuple[CrmDeal, ...]
    crm_activities: tuple[CrmActivity, ...]
    identity_map: dict[str, str]
    scenario_accounts: dict[str, tuple[str, ...]]
    public_signals: tuple[PublicScenarioSignal, ...]
    scoring_inputs: dict[str, dict[str, str]]
    intelligence_events: tuple[RawSignal, ...]
    matching_components: tuple[CommercialComponent, ...]
    matching_quotes: tuple[HistoricalQuoteContext, ...]
    research_mappings: dict[str, str]
    researched_accounts: tuple[ResearchAccount, ...]
    watch_profiles: tuple[AccountWatchProfile, ...]
    public_facilities: tuple[AccountFacility, ...]
    reference_accounts: tuple[CanonicalAccount, ...]
    reference_facilities: tuple[AccountFacility, ...]
    rich_scenarios: dict[str, RichScenario]


def build_sample_environment() -> SampleEnvironment:
    accounts, research_mappings, researched_accounts = build_researched_canonical_accounts()
    accounts, public_facilities = apply_facility_feed_enrichment(accounts, research_mappings)
    reference = load_reference_import()
    existing = {item.id: item for item in accounts}
    merged_accounts: list[CanonicalAccount] = list(accounts)
    for reference_account in reference.accounts:
        current = existing.get(reference_account.id)
        if current is None:
            merged_accounts.append(reference_account)
            existing[reference_account.id] = reference_account
            continue
        aliases = current.public_identity.aliases if current.public_identity else ()
        reference_aliases = reference_account.public_identity.aliases if reference_account.public_identity else ()
        identity = replace(current.public_identity, aliases=tuple({item.value: item for item in (*aliases, *reference_aliases)}.values())) if current.public_identity else reference_account.public_identity
        updated = replace(
            current,
            industries=tuple(dict.fromkeys((*current.industries, *reference_account.industries))),
            public_identity=identity,
            secondary_classifications=tuple(dict.fromkeys((*current.secondary_classifications, *reference_account.secondary_classifications))),
            btx_top_100=reference_account.btx_top_100,
            btx_top_100_provenance=reference_account.btx_top_100_provenance,
        )
        merged_accounts[merged_accounts.index(current)] = updated
        existing[updated.id] = updated
    accounts = tuple(merged_accounts)
    all_facilities = tuple({item.id: item for item in (*public_facilities, *reference.facilities)}.values())
    account_ids, accounts_by_id = {item.id for item in accounts}, {item.id: item for item in accounts}
    units = load_btx_business_units()
    unit_ids = {item.id for item in units}
    btx_facilities = load_btx_facilities(business_unit_ids=unit_ids)
    programs = load_programs(account_ids=account_ids)
    program_ids = {item.id for item in programs}
    components = load_component_classes(business_unit_ids=unit_ids)
    component_ids = {item.id for item in components}
    capabilities = load_capabilities(business_unit_ids=unit_ids)
    edges = load_relationship_edges(account_ids=account_ids, program_ids=program_ids)
    contexts = load_commercial_contexts(account_ids=account_ids, business_unit_ids=unit_ids)
    paperless_accounts, quotes = load_paperless_quotes(accounts_by_id=accounts_by_id, business_unit_ids=unit_ids, program_ids=program_ids, component_ids=component_ids)
    orders = load_orders(account_ids=account_ids, business_unit_ids=unit_ids, program_ids=program_ids, component_ids=component_ids, quote_ids={item.id for item in quotes})
    crm_companies, crm_contacts, crm_deals, crm_activities = load_crm(account_ids=account_ids, business_unit_ids=unit_ids, program_ids=program_ids)
    rich_scenarios = {item.research_account_id: item for item in RICH_SCENARIOS}
    unknown_scenarios = set(rich_scenarios) - account_ids
    if unknown_scenarios:
        raise ValueError(f"curated scenarios have unknown accounts: {sorted(unknown_scenarios)}")
    # Existing account relationship semantics remain public-only; BTX links come from sourced commercial records.
    active_bu_by_account: dict[str, set[str]] = {}
    for context in contexts: active_bu_by_account.setdefault(context.account_id, set()).add(context.business_unit)
    accounts = tuple(replace(item, relationship=AccountRelationship.PUBLIC_MARKET, business_units=tuple(sorted(active_bu_by_account.get(item.id, ())))) for item in accounts)
    scenario_accounts = {
        "southwest-trip": ("anduril-industries", "rocket-lab-usa", "general-atomics"),
        "medical-whitespace": ("medtronic",),
        "defense-award-quote": ("lockheed-martin",),
        "semiconductor-expansion": ("intel",),
        "dormant-customer": ("applied-materials",),
        "quote-follow-up": ("ge-aerospace",),
        "cross-bu-conflict": ("boeing",),
        "strong-external-weak-internal": ("intel",),
        "strong-internal-weak-external": ("lam-research",),
        "missing-unresolved-conflicting": ("symbotic", "intel"),
    }
    scoring_inputs = {account_id: scenario.simulated_score_inputs for account_id, scenario in rich_scenarios.items() if scenario.simulated_score_inputs}
    public_signals = tuple(PublicScenarioSignal(scenario.event.source_id, account_id, scenario.event.source_url, primary_market_label(accounts_by_id[account_id].industries), accounts_by_id[account_id].provenance) for account_id, scenario in rich_scenarios.items())
    quote = next(item for item in quotes if item.account_id == "lockheed-martin" and item.line_items)
    line = quote.line_items[0]
    matching_components = (CommercialComponent(f"component-{line.id}", quote.account_id, quote.program_id, line.part_number, line.component_class_id, None, None, line.component_class_id, line.provenance.evidence_state, (line.provenance.source_record_id,), line.provenance, tuple(item.id for item in capabilities if quote.business_unit in item.business_units)), CommercialComponent(f"component-structured-{line.id}", quote.account_id, quote.program_id, None, line.component_class_id, None, None, line.component_class_id, line.provenance.evidence_state, (line.provenance.source_record_id,), line.provenance, tuple(item.id for item in capabilities if quote.business_unit in item.business_units)))
    matching_quotes = (HistoricalQuoteContext(quote.id, quote.account_id, quote.business_unit, line.part_number, line.component_class_id, None, None, line.component_class_id, (quote.provenance.source_record_id,), quote.provenance),)
    public_facilities_by_account: dict[str, list[str]] = {}
    for facility in public_facilities: public_facilities_by_account.setdefault(facility.account_id, []).append(facility.id)
    recipients = load_usaspending_recipient_identities()
    watch_profiles = tuple(AccountWatchProfile(item.id, item.legal_name, aliases=tuple(field.value for field in item.public_identity.aliases) if item.public_identity else (), domain=item.domain, newsroom_url=item.public_identity.newsroom_url.value if item.public_identity and item.public_identity.newsroom_url else None, investor_relations_url=item.public_identity.investor_relations_url.value if item.public_identity and item.public_identity.investor_relations_url else None, official_feed_urls=tuple(field.value for field in item.public_identity.official_feed_urls) if item.public_identity else (), facilities=tuple(public_facilities_by_account.get(item.id, ())), industries=item.industries, usaspending_recipient_names=tuple(identity.recipient_legal_name for identity in recipients.get(item.id, ())), usaspending_recipient_sources=tuple((identity.recipient_legal_name, identity.source_url) for identity in recipients.get(item.id, ()))) for item in accounts)
    return SampleEnvironment(accounts, all_facilities, contexts, paperless_accounts, quotes, orders, units, btx_facilities, capabilities, programs, components, edges, crm_companies, crm_contacts, crm_deals, crm_activities, {f"public:{item.legal_name.lower()}": item.id for item in accounts}, scenario_accounts, public_signals, scoring_inputs, tuple(item.event for item in rich_scenarios.values()), matching_components, matching_quotes, research_mappings, researched_accounts, watch_profiles, public_facilities, reference.accounts, reference.facilities, rich_scenarios)
