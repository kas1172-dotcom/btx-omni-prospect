from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProviderStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTH_FAILED = "AUTH_FAILED"
    TIMEOUT = "TIMEOUT"
    QUOTA = "QUOTA"
    UNAVAILABLE = "UNAVAILABLE"


class ReadIntent(StrEnum):
    """Only existing governed read routes may be selected by a language provider."""

    ACCOUNT_OVERVIEW = "ACCOUNT_OVERVIEW"
    ACCOUNT_INTELLIGENCE = "ACCOUNT_INTELLIGENCE"
    ACCOUNT_SIGNIFICANCE = "ACCOUNT_SIGNIFICANCE"
    ACCOUNT_NEXT_ACTION = "ACCOUNT_NEXT_ACTION"
    ACCOUNT_ACTIONS = "ACCOUNT_ACTIONS"
    ACCOUNT_QUOTES = "ACCOUNT_QUOTES"
    SCREEN_SUMMARY = "SCREEN_SUMMARY"
    GENERAL_OVERVIEW = "GENERAL_OVERVIEW"


class TechnicalBasis(StrEnum):
    """Whether a technical item is stated by evidence or an AI hypothesis."""

    SOURCE_STATED = "SOURCE_STATED"
    MODEL_INFERRED = "MODEL_INFERRED"


class ExplanationType(StrEnum):
    CUSTOMER_ATTRACTIVENESS = "CUSTOMER_ATTRACTIVENESS"
    FEDERAL_OPPORTUNITY_RELEVANCE = "FEDERAL_OPPORTUNITY_RELEVANCE"
    TECHNICAL_OPPORTUNITY_FIT = "TECHNICAL_OPPORTUNITY_FIT"
    RELATIONSHIP_PATH = "RELATIONSHIP_PATH"
    SIGNAL_PRIORITY = "SIGNAL_PRIORITY"


class LanguageProviderError(RuntimeError):
    """Safe provider failure classification; messages never cross the API boundary."""

    def __init__(self, status: ProviderStatus) -> None:
        super().__init__(status.value)
        self.status = status


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str


@dataclass(frozen=True)
class IntentInterpretationRequest:
    question: str
    recent_turns: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True)
class IntentInterpretation:
    intent: ReadIntent
    entity_text: str | None = None


@dataclass(frozen=True)
class GroundedSynthesisRequest:
    question: str
    governed_answer: str
    evidence_ids: tuple[str, ...]
    missingness: tuple[str, ...]
    recent_turns: tuple[ConversationTurn, ...] = ()
    public_research: tuple[PublicWebFinding, ...] = ()


@dataclass(frozen=True)
class PublicWebResearchRequest:
    """Bounded read-only query over public web content; content is never authority."""

    query: str
    subject_display_name: str | None = None
    governed_context: tuple[str, ...] = ()
    max_findings: int = 5

    def __post_init__(self) -> None:
        if not self.query.strip() or len(self.query) > 800:
            raise ValueError("Public research query exceeds bounds.")
        if (
            self.subject_display_name is not None
            and len(self.subject_display_name) > 300
        ):
            raise ValueError("Public research subject exceeds bounds.")
        if not 1 <= self.max_findings <= 6 or len(self.governed_context) > 8:
            raise ValueError("Public research collection exceeds bounds.")
        if any(not item.strip() or len(item) > 600 for item in self.governed_context):
            raise ValueError("Public research context exceeds bounds.")


@dataclass(frozen=True)
class PublicWebFinding:
    """Cited public finding returned by a provider; it is not a canonical Omni fact."""

    evidence_id: str
    title: str
    url: str
    publisher: str
    extract: str
    retrieval_provenance: str = "GEMINI_GOOGLE_SEARCH"

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or len(self.evidence_id) > 160:
            raise ValueError("Public finding ID is invalid.")
        if (
            not self.title.strip()
            or len(self.title) > 500
            or not self.url.startswith(("https://", "http://"))
        ):
            raise ValueError("Public finding citation is invalid.")
        if (
            not self.publisher.strip()
            or len(self.publisher) > 240
            or not self.extract.strip()
            or len(self.extract) > 1600
        ):
            raise ValueError("Public finding content exceeds bounds.")


@dataclass(frozen=True)
class PublicWebResearchResult:
    findings: tuple[PublicWebFinding, ...]
    provider: str
    model: str
    search_provenance: str = "GEMINI_GOOGLE_SEARCH"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.findings) > 6:
            raise ValueError("Public research findings exceed bounds.")
        if len(self.limitations) > 6 or any(
            not item.strip() or len(item) > 500 for item in self.limitations
        ):
            raise ValueError("Public research limitations exceed bounds.")


@dataclass(frozen=True)
class GovernedExplanationRequest:
    """Bounded facts from a deterministic Omni result, never raw application state."""

    explanation_type: ExplanationType
    subject_type: str
    subject_display_name: str
    deterministic_result: str
    deterministic_status: str
    numeric_value: str | None = None
    score_unit: str | None = None
    configuration_version: str | None = None
    key_drivers: tuple[str, ...] = ()
    limiting_factors: tuple[str, ...] = ()
    deterministic_matches: tuple[str, ...] = ()
    missingness: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    data_mode: str = "UNAVAILABLE"
    hypothesis_or_calibration: str | None = None
    style: str = "SELLER_CONCISE"
    contract_version: str = "governed-explanation-v1"
    prompt_version: str = "governed-explanation-prompt-v1"

    def __post_init__(self) -> None:
        if (
            not self.subject_type.strip()
            or not self.subject_display_name.strip()
            or len(self.subject_display_name) > 300
        ):
            raise ValueError("Governed explanation subject is invalid.")
        if (
            not self.deterministic_result.strip()
            or len(self.deterministic_result) > 6000
        ):
            raise ValueError("Governed explanation result exceeds bounds.")
        if any(
            value is not None and (not value.strip() or len(value) > 160)
            for value in (
                self.numeric_value,
                self.score_unit,
                self.configuration_version,
                self.hypothesis_or_calibration,
                self.style,
                self.contract_version,
                self.prompt_version,
            )
        ):
            raise ValueError("Governed explanation metadata exceeds bounds.")
        for values in (
            self.key_drivers,
            self.limiting_factors,
            self.deterministic_matches,
            self.missingness,
            self.evidence_ids,
        ):
            if len(values) > 12 or any(
                not value.strip() or len(value) > 600 for value in values
            ):
                raise ValueError("Governed explanation collection exceeds bounds.")


@dataclass(frozen=True)
class GovernedExplanation:
    summary: str
    key_drivers: tuple[str, ...]
    limitations: tuple[str, ...]
    what_to_consider: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    explanation_type: ExplanationType
    provider: str
    model: str
    contract_version: str

    def __post_init__(self) -> None:
        if not self.summary.strip() or len(self.summary) > 1200:
            raise ValueError("Governed explanation summary exceeds bounds.")
        for values in (self.key_drivers, self.limitations, self.what_to_consider):
            if len(values) > 6 or any(
                not value.strip() or len(value) > 500 for value in values
            ):
                raise ValueError("Governed explanation output exceeds bounds.")


@dataclass(frozen=True)
class PublicEvidenceRecord:
    """Bounded public evidence supplied as content, never as instructions."""

    evidence_id: str
    title: str
    extract: str
    source_url: str | None = None
    provenance: str | None = None


@dataclass(frozen=True)
class TechnicalCandidate:
    name: str
    basis: TechnicalBasis
    reason: str
    source_support: str
    evidence_ids: tuple[str, ...] = ()
    parent_system: str | None = None
    parent_product: str | None = None
    manufacturing_family: str | None = None

    def __post_init__(self) -> None:
        for value in (self.name, self.reason, self.source_support):
            if not value.strip() or len(value) > 500:
                raise ValueError(
                    "Technical candidate text is invalid or exceeds bounds."
                )
        if len(self.evidence_ids) > 8 or any(
            not item.strip() or len(item) > 160 for item in self.evidence_ids
        ):
            raise ValueError("Technical candidate evidence IDs exceed bounds.")
        if any(
            value is not None and len(value) > 240
            for value in (
                self.parent_system,
                self.parent_product,
                self.manufacturing_family,
            )
        ):
            raise ValueError("Technical candidate context exceeds bounds.")


@dataclass(frozen=True)
class TechnicalDecompositionRequest:
    """Model-neutral, public-only technical interpretation contract."""

    event_id: str
    event_type: str
    canonical_customer_name: str | None
    canonical_program_name: str | None
    market: str | None
    evidence: tuple[PublicEvidenceRecord, ...]
    contract_version: str = "technical-decomposition-v1"
    prompt_version: str = "technical-decomposition-prompt-v1"

    def __post_init__(self) -> None:
        if not self.event_id.strip() or len(self.event_id) > 160:
            raise ValueError("Technical decomposition event ID is invalid.")
        if not self.evidence or len(self.evidence) > 6:
            raise ValueError(
                "Technical decomposition requires one to six public evidence records."
            )


@dataclass(frozen=True)
class TechnicalDecompositionResult:
    event_summary: str
    product_candidates: tuple[TechnicalCandidate, ...] = ()
    program_candidates: tuple[TechnicalCandidate, ...] = ()
    technical_systems: tuple[TechnicalCandidate, ...] = ()
    component_candidates: tuple[TechnicalCandidate, ...] = ()
    uncertainties: tuple[str, ...] = ()
    provider: str = "gemini"
    model: str = ""

    def __post_init__(self) -> None:
        if not self.event_summary.strip() or len(self.event_summary) > 1_200:
            raise ValueError(
                "Technical decomposition summary is invalid or exceeds bounds."
            )
        for collection in (
            self.product_candidates,
            self.program_candidates,
            self.technical_systems,
            self.component_candidates,
        ):
            if len(collection) > 8:
                raise ValueError("Technical decomposition list exceeds bounds.")
        if len(self.uncertainties) > 8 or any(
            not value.strip() or len(value) > 500 for value in self.uncertainties
        ):
            raise ValueError("Technical decomposition uncertainty exceeds bounds.")


@dataclass(frozen=True)
class LanguageResult:
    content: str
    provider: str
    model: str
    evidence_ids: tuple[str, ...]


class LanguageProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    def interpret(
        self, request: IntentInterpretationRequest
    ) -> IntentInterpretation: ...

    def synthesize(self, request: GroundedSynthesisRequest) -> LanguageResult: ...

    def research_public_web(
        self, request: PublicWebResearchRequest
    ) -> PublicWebResearchResult: ...

    def decompose_technical_opportunity(
        self, request: TechnicalDecompositionRequest
    ) -> TechnicalDecompositionResult: ...

    def explain_governed_result(
        self, request: GovernedExplanationRequest
    ) -> GovernedExplanation: ...
