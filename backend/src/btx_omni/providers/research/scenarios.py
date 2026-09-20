"""Curated public-company POC scenarios; BTX selections are explicitly simulated."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from btx_omni.domain.common import EvidenceState
from btx_omni.modules.intelligence.signals import (
    RawSignal,
    SignalKind,
    SourceValidationState,
)


@dataclass(frozen=True)
class RichScenario:
    research_account_id: str
    reason_for_attention: str
    recommended_next_step: str
    event: RawSignal
    simulated_score_inputs: dict[str, str]
    exclusion_reason: str | None = None


def _all(value: str = "ROUTINE", *, adjacency: str = "COLD_PROSPECT") -> dict[str, str]:
    return {
        "program_durability.expected_production_horizon": "TEN_PLUS_YEARS", "program_durability.repeat_production_pattern": "ESTABLISHED_RECURRING", "program_durability.commitment_strength": "FUNDED_AWARDED_CONTRACTED", "program_durability.industry_specific_maturity_evidence": "STRONG_EVIDENCE",
        "btx_manufacturing_fit.material_match": value, "btx_manufacturing_fit.process_tolerance_match": value, "btx_manufacturing_fit.certification_compliance_fit": "ALL_MET", "btx_manufacturing_fit.volume_compatibility": "NORMAL_RANGE",
        "addressable_btx_work.btx_relevant_component_content": "MULTIPLE_FAMILIES", "addressable_btx_work.repeat_volume_potential": "LARGE_RECURRING", "addressable_btx_work.cross_bu_applicability": "TWO_PLUS_BU", "addressable_btx_work.make_buy_propensity": "SOURCES_EXTERNALLY",
        "program_momentum.recent_awards_funding_production_increases": "CLEAR_POSITIVE_RECENT", "program_momentum.program_linked_hiring_staffing": "VISIBLE_SURGE", "program_momentum.production_delivery_milestones": "SCALE_UP_OR_MAJOR", "program_momentum.regulatory_funding_events": "MATERIALLY_IMPROVES",
        "strategic_target_fit": "CORE_TARGET_ARCHETYPE", "btx_commercial_adjacency": adjacency,
    }


def _event(
    source_id: str,
    kind: SignalKind,
    title: str,
    url: str,
    company: str,
    date: tuple[int, int, int],
    summary: str,
    source_validation_state: SourceValidationState = SourceValidationState.NEEDS_RESEARCH,
    *,
    business_relevance: str | None = None,
) -> RawSignal:
    return RawSignal(
        source_id, kind, title, url, datetime(*date, tzinfo=UTC), company, None,
        EvidenceState.CONFIRMED, summary, source_validation_state, business_relevance,
    )


IDEAL = _all()
STRONG = {**_all(), "program_durability.expected_production_horizon": "FIVE_TO_NINE_YEARS", "program_momentum.program_linked_hiring_staffing": "STEADY", "strategic_target_fit": "STRONG_TARGET_ARCHETYPE"}
WARM_DECLINING = {**_all(adjacency="EXISTING_ONE_BU_ACTIVE"), "program_durability.expected_production_horizon": "TWO_TO_FOUR_YEARS", "program_momentum.recent_awards_funding_production_increases": "REDUCTION_OR_CANCELLATION", "program_momentum.production_delivery_milestones": "DELAY_SLIPPAGE", "strategic_target_fit": "PLAUSIBLE_UNCLEAR"}
POOR_FIT = {**_all(value="KNOWN_MISMATCH"), "btx_manufacturing_fit.certification_compliance_fit": "MAJOR_GAP", "btx_manufacturing_fit.volume_compatibility": "POOR_FIT", "addressable_btx_work.btx_relevant_component_content": "MINIMAL", "addressable_btx_work.repeat_volume_potential": "ONE_OFF", "addressable_btx_work.cross_bu_applicability": "WEAK_OR_NONE", "addressable_btx_work.make_buy_propensity": "MOSTLY_CAPTIVE", "program_momentum.recent_awards_funding_production_increases": "NO_MATERIAL_CHANGE", "strategic_target_fit": "UNLIKELY"}
LOW_EVIDENCE = {"strategic_target_fit": "STRONG_TARGET_ARCHETYPE", "btx_commercial_adjacency": "COLD_PROSPECT"}


SCENARIOS = (
    RichScenario("boeing", "Public FAA production oversight update merits an evidence-led account review.", "Review the public source and identify the appropriate procurement role target.", _event("FAA_BOEING", SignalKind.INDUSTRY_UPDATE, "FAA production oversight update", "https://www.faa.gov/newsroom/after-months-safety-review-faa-allows-boeing-resume-issuing-certificates-new-airplanes", "Boeing", (2025, 3, 14), "FAA public update concerning Boeing production oversight."), IDEAL),
    RichScenario("ge-aerospace", "NASA public propulsion research award provides a concrete program context.", "Validate public program relevance and route to a Commercial Aerospace role-family target.", _event("NASA_PROPULSION", SignalKind.AWARD_CONTRACT, "NASA propulsion research contract announcement", "https://www.nasa.gov/news-release/nasa-awards-propulsion-research-contracts-to-five-firms/", "GE Aerospace", (2024, 9, 25), "NASA announcement naming propulsion research contractors."), STRONG),
    RichScenario("lockheed-martin", "NASA CLPS and public supplier evidence warrant coordinated review, not a BTX relationship claim.", "Coordinate a simulated cross-BU account plan after reviewing the public sources.", _event("NASA_CLPS", SignalKind.AWARD_CONTRACT, "NASA CLPS provider context", "https://www.nasa.gov/commercial-lunar-payload-services/clps-providers/", "Lockheed Martin", (2025, 1, 1), "NASA public CLPS provider information."), {**IDEAL, "btx_commercial_adjacency": "EXISTING_MULTI_BU_ACTIVE"}),
    RichScenario("northrop-grumman", "NASA VADR and DoD sources show public government program context.", "Review public program evidence; do not assume commercial history.", _event("NASA_VADR", SignalKind.AWARD_CONTRACT, "NASA VADR launch services context", "https://www.nasa.gov/vadr-venture-class-acquisition-of-dedicated-and-rideshare-launch-services/", "Northrop Grumman", (2024, 6, 13), "NASA public VADR launch-services information."), STRONG),
    RichScenario("anduril-industries", "DoD public microelectronics context is relevant but manufacturing fit remains a POC hypothesis.", "Assess fit with a role-family target and retain material/process gaps.", _event("DOD_MICRO", SignalKind.INDUSTRY_UPDATE, "DoD microelectronics ecosystem context", "https://www.defense.gov/News/Speeches/Speech/Article/3948717/remarks-by-deputy-secretary-of-defense-kathleen-hicks-at-the-2024-microelectr/", "Anduril Industries", (2024, 10, 29), "DoD public remarks on the microelectronics ecosystem.", SourceValidationState.BROWSER_VERIFIED), POOR_FIT),
    RichScenario("blue-origin", "NASA public provider context supports a strong cold-prospect teaching scenario.", "Research the public program and identify a legitimate public supplier-management channel.", _event("NASA_VADR", SignalKind.AWARD_CONTRACT, "NASA VADR provider context", "https://www.nasa.gov/vadr-venture-class-acquisition-of-dedicated-and-rideshare-launch-services/", "Blue Origin", (2024, 6, 13), "NASA public VADR provider information."), STRONG),
    RichScenario("rocket-lab-usa", "NASA VADR context provides a public event to review.", "Treat this as needs research until public manufacturing-fit evidence is sufficient.", _event("NASA_VADR", SignalKind.AWARD_CONTRACT, "NASA VADR provider context", "https://www.nasa.gov/vadr-venture-class-acquisition-of-dedicated-and-rideshare-launch-services/", "Rocket Lab USA", (2024, 6, 13), "NASA public VADR provider information."), LOW_EVIDENCE),
    RichScenario("intel", "Commerce announced CHIPS incentives for Intel; this is a public expansion signal.", "Review public expansion evidence and qualify the manufacturing-fit hypothesis.", _event("CHIPS_INTEL", SignalKind.EXPANSION, "Commerce CHIPS incentives award", "https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-intel", "Intel", (2024, 11, 26), "Commerce public CHIPS incentives announcement.", SourceValidationState.AUTOMATION_BLOCKED), IDEAL),
    RichScenario("tsmc-arizona", "Commerce CHIPS incentives provide Phoenix expansion context.", "Use verified public facility context for seller planning; no BTX relationship is implied.", _event("CHIPS_TSMC", SignalKind.EXPANSION, "Commerce CHIPS incentives award", "https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-tsmc", "TSMC Arizona", (2024, 11, 15), "Commerce public CHIPS incentives announcement.", SourceValidationState.BROWSER_VERIFIED), STRONG),
    RichScenario("applied-materials", "Commerce awarded Applied Materials $100 million to develop and scale silicon-core substrate technology for advanced semiconductor packaging in Santa Clara.", "Confirm whether the silicon-core substrate program creates sourced precision hardware, tooling, or equipment-support needs before selecting a BTX business unit.", _event("CHIPS_APPLIED", SignalKind.EXPANSION, "Applied Materials receives $100 million advanced-packaging award", "https://www.commerce.gov/news/press-releases/2025/01/us-department-commerce-announces-14-billion-final-awards-support-next", "Applied Materials", (2025, 1, 16), "Commerce awarded Applied Materials $100 million to develop and scale silicon-core substrate technology for advanced packaging and 3D heterogeneous integration in Santa Clara, California.", SourceValidationState.BROWSER_VERIFIED, business_relevance="The funded silicon-core substrate work could create precision hardware, tooling, or equipment-support demand adjacent to BTX capabilities; sourcing scope and the right BTX business unit are not yet established."), WARM_DECLINING),
    RichScenario("medtronic", "The SEC annual report is a verified public-company context, not a sales signal.", "Use a medical-device role-family target; obtain more public evidence before a recommendation.", _event("SEC_MDT", SignalKind.FINANCIAL_REPORT, "Medtronic annual report filed", "https://www.sec.gov/Archives/edgar/data/1613103/000161310325000091/mdt-20250425.htm", "Medtronic", (2025, 4, 25), "SEC-filed annual report.", SourceValidationState.BROWSER_VERIFIED), LOW_EVIDENCE),
    RichScenario("symbotic", "The SEC annual report provides current public industrial-automation context.", "Review public disclosure and use a role-family target for initial research.", _event("SEC_SYMBOTIC", SignalKind.FINANCIAL_REPORT, "Symbotic annual report filed", "https://www.sec.gov/Archives/edgar/data/1837240/000183724025000278/sym-20250927.htm", "Symbotic", (2025, 9, 27), "SEC-filed annual report.", SourceValidationState.BROWSER_VERIFIED), {}, "Excluded from this POC score: no simulated manufacturing-fit selection has been approved for this scenario."),
)
