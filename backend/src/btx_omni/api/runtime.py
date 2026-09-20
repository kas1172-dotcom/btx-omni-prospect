"""Shared bounded POC runtime for API routers; CONNECTED never falls back to SAMPLE."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.ai.config import AiConfig
from btx_omni.ai.registry import get_ai_provider
from btx_omni.core.config import Settings
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.modules.commercial.read import (
    CommercialAccountSnapshot,
    CommercialReadService,
)
from btx_omni.modules.communications.service import CommunicationService
from btx_omni.modules.intelligence.technical_fit import TechnicalDecompositionService
from btx_omni.modules.markets.service import MarketService
from btx_omni.modules.work.service import WorkService
from btx_omni.monitor.catalog import MonitorCatalog
from btx_omni.monitor.entity_candidates import EntityCandidateResolver
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import REGISTRY, SecEdgarAdapter, UsaSpendingAdapter
from btx_omni.monitor.targeting import StrategicWatchUniverse
from btx_omni.monitor.usaspending import recipient_query_names
from btx_omni.persistence.account_planning import AccountPlanningRepository
from btx_omni.persistence.actions import SqlActionRepository
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.persistence.communications import SqlCommunicationRepository
from btx_omni.persistence.database import create_database_engine
from btx_omni.persistence.durable_accounts import DurablePublicAccountRepository
from btx_omni.persistence.durable_programs import DurableCanonicalProgramRepository
from btx_omni.persistence.itineraries import ItineraryRepository
from btx_omni.persistence.market_series import MarketSeriesRepository
from btx_omni.persistence.network_import import NetworkImportRepository
from btx_omni.persistence.omni_memory import OmniMemoryRepository
from btx_omni.persistence.omni_runs import OmniRunRepository
from btx_omni.persistence.reference_fields import ReferenceFieldRepository
from btx_omni.persistence.work_feedback import SuggestionFeedbackRepository
from btx_omni.providers.sample.environment import (
    SampleEnvironment,
    build_sample_environment,
)
from btx_omni.security.sessions import SessionStore


@dataclass
class PocRuntime:
    settings: Settings
    sample: SampleEnvironment = field(default_factory=build_sample_environment)
    work: WorkService = field(init=False)
    communications: CommunicationService = field(init=False)
    communication_repository: SqlCommunicationRepository = field(init=False)
    monitor: MonitorService = field(init=False)
    sessions: SessionStore = field(init=False)
    memory: OmniMemoryRepository = field(init=False)
    omni_runs: OmniRunRepository = field(init=False)
    work_feedback: SuggestionFeedbackRepository = field(init=False)
    itineraries: ItineraryRepository = field(init=False)
    account_planning: AccountPlanningRepository = field(init=False)
    markets: MarketService = field(init=False)
    durable_accounts: DurablePublicAccountRepository | None = field(
        init=False, default=None
    )
    durable_programs: DurableCanonicalProgramRepository | None = field(
        init=False, default=None
    )
    _curated_sample: SampleEnvironment = field(init=False, repr=False)
    _original_sample: SampleEnvironment = field(init=False, repr=False)
    commercial_repository: CommercialImportRepository | None = field(init=False, default=None)
    technical_decomposition: TechnicalDecompositionService = field(init=False)
    network_imports: NetworkImportRepository = field(init=False)

    def __post_init__(self) -> None:
        if self.settings.sample_enhancement_enabled and self.settings.data_mode.upper() == 'SAMPLE':
            from btx_omni.providers.sample.enhancement import enhance_environment
            self.sample = enhance_environment(self.sample, anchor=self.settings.demo_as_of_date)
        self._curated_sample = self.sample
        self._original_sample = self.sample
        self.sessions = SessionStore(self.settings)
        self.technical_decomposition = TechnicalDecompositionService(
            components=self.sample.component_classes,
            business_units=self.sample.business_units,
            capabilities=self.sample.capabilities,
            facilities=self.sample.facilities,
        )
        application_engine = create_database_engine(self.settings)
        self.network_imports = NetworkImportRepository(application_engine, self.sample.watch_profiles)
        self.memory = OmniMemoryRepository(application_engine)
        self.omni_runs = OmniRunRepository(application_engine)
        self.reference_fields = ReferenceFieldRepository(application_engine)
        self.work_feedback = SuggestionFeedbackRepository(application_engine)
        self.itineraries = ItineraryRepository(application_engine)
        self.account_planning = AccountPlanningRepository(application_engine)
        self.markets = MarketService(MarketSeriesRepository(application_engine), worker_enabled=self.settings.market_refresh_enabled,
                                     scheduler_configured=self.settings.monitor_schedule_configured)
        if self.settings.commercial_durable_state_enabled:
            self.commercial_repository = CommercialImportRepository(application_engine)
            self.refresh_commercial_catalog()
        self.work = WorkService(SqlActionRepository(application_engine))
        self.communication_repository = SqlCommunicationRepository(application_engine)
        self.communications = CommunicationService(self.communication_repository)
        engine = (
            application_engine if self.settings.monitor_durable_state_enabled else None
        )
        repository = MonitorRepository(engine) if engine else None
        self.durable_accounts = (
            DurablePublicAccountRepository(engine) if engine else None
        )
        self.durable_programs = (
            DurableCanonicalProgramRepository(engine) if engine else None
        )
        if self.durable_accounts and self.durable_programs:
            try:
                self.refresh_durable_catalog()
            except SQLAlchemyError:
                self.durable_accounts = None
                self.durable_programs = None
        watch_universe = StrategicWatchUniverse(
            accounts=self.sample.accounts,
            profiles=self.sample.watch_profiles,
            facilities=self.sample.facilities,
            scenario_account_ids=frozenset(self.sample.rich_scenarios),
        )
        usa_targets = watch_universe.targets_for(
            REGISTRY["usaspending"].definition,
            cap=self.settings.monitor_source_target_limit,
        )
        usa_profiles = tuple(item.profile for item in usa_targets)
        registry = dict(REGISTRY)
        registry["usaspending"] = UsaSpendingAdapter(
            recipient_names=recipient_query_names(usa_profiles)
        )
        sec_targets = tuple(
            target
            for target in watch_universe.targets_for(
                REGISTRY["sec_edgar"].definition, cap=10_000
            )
            if target.profile.sec_cik
        )[: self.settings.monitor_source_target_limit]
        registry["sec_edgar"] = SecEdgarAdapter(
            targets=tuple((target.profile.sec_cik, target.legal_name) for target in sec_targets if target.profile.sec_cik)
        )
        self.monitor = MonitorService(
            self.settings,
            registry=registry,
            repository=repository,
            watch_profiles=usa_profiles,
            catalog=MonitorCatalog(
                self.sample.watch_profiles, self.sample.programs, self.sample.facilities
            ),
            entity_candidate_resolver=EntityCandidateResolver(
                get_ai_provider(AiConfig.from_settings(self.settings)), repository,
                self.sample.watch_profiles,
                cap=self.settings.monitor_entity_candidate_resolution_cap,
            ),
        )
        self.monitor.watch_targets = {
            "usaspending": usa_targets,
            "sec_edgar": sec_targets,
        }
        if repository:
            try:
                self.monitor.hydrate_events()
            except SQLAlchemyError:
                # The Monitor health route retains the existing durable-state
                # unavailable/degraded behavior; do not fabricate live events.
                pass

    def refresh_durable_accounts(self) -> None:
        """Compatibility name for callers refreshing the durable canonical catalog."""
        self.refresh_durable_catalog()

    def refresh_durable_catalog(self) -> None:
        """Recompose the one canonical Account and Program universe after a durable write."""
        if not self.durable_accounts or not self.durable_programs:
            return
        persisted = tuple(item.account for item in self.durable_accounts.accounts())
        durable_programs = tuple(
            item.program for item in self.durable_programs.programs()
        )
        ids = {item.id for item in self._curated_sample.accounts}
        if ids & {item.id for item in persisted}:
            raise ValueError(
                "durable Account ID collides with the curated canonical universe."
            )
        curated_program_ids = {item.id for item in self._curated_sample.programs}
        if curated_program_ids & {item.id for item in durable_programs}:
            raise ValueError(
                "durable Program ID collides with the curated canonical universe."
            )
        if {item.name.casefold() for item in self._curated_sample.programs} & {
            item.name.casefold() for item in durable_programs
        }:
            raise ValueError(
                "durable Program name collides with the curated canonical universe."
            )
        durable_profiles = tuple(
            AccountWatchProfile(
                item.id,
                item.legal_name,
                aliases=tuple(field.value for field in item.public_identity.aliases)
                if item.public_identity
                else (),
                domain=item.domain,
                source_native_identifiers=tuple(
                    field.source_native_identifier
                    for field in item.public_identity.source_native_identifiers
                    if field.source_native_identifier
                )
                if item.public_identity
                else (),
                industries=item.industries,
            )
            for item in persisted
        )
        self.sample = replace(
            self._curated_sample,
            accounts=(*self._curated_sample.accounts, *persisted),
            programs=(*self._curated_sample.programs, *durable_programs),
            identity_map={
                **self._curated_sample.identity_map,
                **{
                    f"public:{item.legal_name.casefold()}": item.id
                    for item in persisted
                },
            },
            watch_profiles=(*self._curated_sample.watch_profiles, *durable_profiles),
        )
        if hasattr(self, "monitor"):
            self.monitor.watch_profiles = self.sample.watch_profiles
            self.monitor.catalog = MonitorCatalog(
                self.sample.watch_profiles, self.sample.programs, self.sample.facilities
            )

    def environment(self) -> SampleEnvironment:
        if self.settings.data_mode.upper() != "SAMPLE":
            raise HTTPException(
                503, "CONNECTED mode is unavailable: no live providers are configured."
            )
        if self.commercial_repository:
            try:
                self.refresh_commercial_catalog()
            except (SQLAlchemyError, ValueError) as error:
                raise HTTPException(503, "Persisted commercial data is unavailable; retry shortly.") from error
        return self.sample

    def refresh_commercial_catalog(self) -> None:
        """Invalidate every shared commercial consumer on a committed revision."""
        if not self.commercial_repository:
            return
        revision = self.commercial_repository.revision()
        crm_mappings = self.commercial_repository.crm_mappings()
        if revision == self._curated_sample.commercial_revision and crm_mappings == getattr(self, '_last_crm_mappings', None):
            return
        revision, records, crm_mappings = self.commercial_repository.snapshot(include_crm=True)
        if not records:
            raise ValueError("Durable commercial mode requires a qualified import")
        self._curated_sample = project_commercial_records(self._original_sample, records, revision=revision, crm_mappings=crm_mappings)
        self._last_crm_mappings = crm_mappings
        self.sample = self._curated_sample
        self.refresh_durable_catalog()
        self.technical_decomposition = TechnicalDecompositionService(
            components=self.sample.component_classes,
            business_units=self.sample.business_units,
            capabilities=self.sample.capabilities,
            facilities=self.sample.facilities,
        )
        if hasattr(self, "monitor"):
            self.monitor.catalog = MonitorCatalog(
                self.sample.watch_profiles, self.sample.programs, self.sample.facilities
            )

    def commercial_account_snapshot(self, canonical_account_id: str) -> CommercialAccountSnapshot:
        """Return the configured provider-neutral commercial read projection."""
        return CommercialReadService(self.environment()).account_snapshot(canonical_account_id)

    @staticmethod
    def observed_at() -> datetime:
        from btx_omni.core.clock import as_of_datetime
        return as_of_datetime()
