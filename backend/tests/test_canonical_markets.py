from __future__ import annotations

import pytest

from btx_omni.domain.markets import (
    PRIMARY_MARKET_ORDER,
    PRIMARY_MARKETS,
    AmbiguousMarketError,
    normalize_source_market,
)
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.providers.sample.environment import build_sample_environment


def test_canonical_market_contract_has_stable_product_order() -> None:
    assert PRIMARY_MARKET_ORDER == (
        "Defense",
        "Commercial Aerospace",
        "Space",
        "Robotics",
        "Semiconductor",
        "Medical",
        "Energy",
    )
    assert PRIMARY_MARKETS == frozenset(PRIMARY_MARKET_ORDER)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("Commercial Aerospace", "Commercial Aerospace"),
        ("commercial_aerospace", "Commercial Aerospace"),
        ("Space Exploration", "Space"),
        ("space", "Space"),
        ("Robotics", "Robotics"),
        ("Semiconductors", "Semiconductor"),
        ("medical", "Medical"),
        ("energy", "Energy"),
    ),
)
def test_unambiguous_source_aliases_normalize(source: str, expected: str) -> None:
    assert normalize_source_market(source) == expected


def test_legacy_aerospace_and_unknown_values_fail_closed() -> None:
    with pytest.raises(AmbiguousMarketError):
        normalize_source_market("Aerospace")
    with pytest.raises(AmbiguousMarketError):
        normalize_source_market("aerospace")
    with pytest.raises(ValueError):
        normalize_source_market("aviation adjacent")


def test_environment_uses_only_canonical_markets_without_changing_ids() -> None:
    environment = build_sample_environment()
    expected_ids = {
        "afit", "anduril-industries", "applied-materials", "asml", "blue-origin",
        "boeing", "boston-scientific", "commonwealth-fusion",
        "ge-aerospace", "ge-vernova", "general-atomics", "intel",
        "intuitive-surgical", "johnson-johnson-medtech", "kla", "l3harris",
        "lam-research", "lockheed-martin", "medtronic", "northrop-grumman",
        "pratt-whitney", "rocket-lab-usa", "rtx-collins-aerospace", "sierra-space",
        "spacex", "spirit-aerosystems", "stryker", "symbotic", "terrapower",
        "textron", "tsmc-arizona", "ula-united-launch-alliance", "westinghouse",
        "zimmer-biomet",
    }
    assert {account.id for account in environment.accounts} == expected_ids
    assert all(set(account.industries) <= PRIMARY_MARKETS for account in environment.accounts)
    symbotic = next(account for account in environment.accounts if account.id == "symbotic")
    assert symbotic.industries == ("Robotics",)
    assert "Robotics" not in symbotic.secondary_classifications
    assert {program.system for program in environment.programs if program.system} <= PRIMARY_MARKETS
    assert {component.industry for component in environment.component_classes if component.industry} <= PRIMARY_MARKETS


def test_ambiguous_component_aerospace_is_not_silently_promoted() -> None:
    environment = build_sample_environment()
    unresolved_ids = {
        "cc-engine-nacelle",
        "cc-structural-airframe",
        "cc-sensor-housing",
        "cc-actuator",
        "cc-aircraft-wing-optimized",
        "cc-custom-fastener",
    }
    assert {
        component.id
        for component in environment.component_classes
        if component.industry is None and component.evidence_state.value == "CONFIRMED"
    } == unresolved_ids


def test_omni_uses_canonical_market_phrasing_without_aerospace_inference() -> None:
    space, _, _ = OmniOrchestrator._cross_account_market({}, "which space customers")
    commercial, _, _ = OmniOrchestrator._cross_account_market(
        {}, "which commercial aerospace customers"
    )
    ambiguous, _, _ = OmniOrchestrator._cross_account_market(
        {}, "which aerospace customers"
    )

    assert space == "Space"
    assert commercial == "Commercial Aerospace"
    assert ambiguous is None
