from decimal import Decimal

import pytest

from btx_omni.modules.relationships.rubric import (
    RouteFactors,
    route_redundancy,
    route_utility,
    select_alternatives,
    sensitivity_report,
)


def route(key, *, strength=3, hops=2, edges=None, nodes=None, sources=None):
    factors = RouteFactors(strength, 3, 3, 2, Decimal(1))
    return {"path_id": key, "factors": factors, "utility": route_utility(factors, hops), "hop_count": hops,
            "eligible": True, "mode": "commercial_fit", "execution_status": "NEEDS_CHECK",
            "edge_lineage": edges or [key], "node_ids": nodes or ["a", key, "b"], "source_lineage": sources or [key]}


def test_exact_rubric_and_longer_stronger_ordering():
    assert route_utility(RouteFactors(3, 3, 3, 2, Decimal(1)), 1) == 100
    assert route_utility(RouteFactors(3, 3, 3, 2, Decimal(1)), 5) == 92
    strong, weak = route("long", hops=5), route("short", strength=1, hops=2)
    assert strong["utility"] > weak["utility"]
    assert select_alternatives([weak, strong])[0]["path_id"] == "long"


def test_no_manufactured_alternatives_or_cross_status_ranking():
    assert select_alternatives([]) == []
    assert len(select_alternatives([route("one")])) == 1
    with pytest.raises(ValueError, match="separately"):
        select_alternatives([route("one"), {**route("two"), "execution_status": "BLOCKED"}])


def test_diversity_raw_utility_stays_separate_and_duplicate_lineage_not_rewarded():
    first = route("a", edges=["shared"], sources=["source"], nodes=["start", "middle", "end"])
    duplicate = {**first, "path_id": "b"}
    alternate = route("c")
    selected = select_alternatives([duplicate, alternate, first])
    assert [r["path_id"] for r in selected] == ["a", "c"]
    assert all(r["utility"] == 98 for r in selected)
    assert route_redundancy(first, duplicate) == 1


def test_empty_overlap_zero_and_sensitivity_is_reported():
    empty = {"edge_lineage": [], "source_lineage": [], "node_ids": ["a", "b"]}
    assert route_redundancy(empty, empty) == 0
    report = sensitivity_report([route("one"), route("two", strength=2, hops=4)])
    assert len(report["variants"]) == 5 and report["first_recommendation_stable"]


def test_null_and_invalid_factors_cannot_raise_a_rank():
    with pytest.raises(ValueError):
        RouteFactors(True, 3, 3, 2, Decimal(1))
    with pytest.raises(ValueError):
        RouteFactors(3, 3, 3, 2, Decimal("NaN"))
    assert route_utility(RouteFactors(2, 2, 1, 0, Decimal(0)), 4) < route_utility(RouteFactors(2, 2, 1, 1, Decimal(1)), 4)
