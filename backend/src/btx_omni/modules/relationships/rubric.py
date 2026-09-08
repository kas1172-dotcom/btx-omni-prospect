"""BTX's provisional commercial route rubric, separate from search and layout."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

RUBRIC_VERSION = "BTX_RELATIONSHIP_POC_1"
COEFFICIENTS = (Decimal(".40"), Decimal(".25"), Decimal(".20"), Decimal(".10"), Decimal(".05"))


@dataclass(frozen=True)
class RouteFactors:
    bottleneck: int
    relevance: int
    evidence: int
    freshness: int
    coverage: Decimal

    def __post_init__(self):
        if any(type(v) is not int or not 0 <= v <= 3 for v in (self.bottleneck, self.relevance, self.evidence)):
            raise ValueError("B/R/E must be ordinal integers0..3")
        if type(self.freshness) is not int or not 0 <= self.freshness <= 2:
            raise ValueError("F must be ordinal integer0..2")
        if not self.coverage.is_finite() or not 0 <= self.coverage <= 1:
            raise ValueError("Coverage must be finite0..1")


def route_utility(factors: RouteFactors, hops: int, *, coefficients=COEFFICIENTS) -> Decimal:
    if not 1 <= hops <= 6 or len(coefficients) != 5 or sum(coefficients) != 1 or any(c < 0 for c in coefficients):
        raise ValueError("Invalid bounded route/rubric configuration")
    values = (Decimal(factors.bottleneck) / 3, Decimal(factors.relevance) / 3,
              Decimal(factors.evidence) / 3, Decimal(factors.freshness) / 2, factors.coverage)
    raw = 100 * sum(c * v for c, v in zip(coefficients, values, strict=True)) - 2 * max(0, hops - 1)
    return min(Decimal(100), max(Decimal(0), raw)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def _jaccard(left, right) -> Decimal:
    a, b = set(left), set(right)
    return Decimal(len(a & b)) / len(a | b) if a or b else Decimal(0)


def route_redundancy(left: dict, right: dict) -> Decimal:
    return (Decimal(".50") * _jaccard(left["edge_lineage"], right["edge_lineage"])
            + Decimal(".30") * _jaccard(left["node_ids"][1:-1], right["node_ids"][1:-1])
            + Decimal(".20") * _jaccard(left["source_lineage"], right["source_lineage"]))


def select_alternatives(routes: list[dict], *, limit: int = 3) -> list[dict]:
    """Greedy MMR-style BTX adaptation; never a claim of global diverse optimum."""
    if not 1 <= limit <= 3:
        raise ValueError("At most three route cards are configured")
    eligible = [r for r in routes if r["eligible"] and r["factors"].bottleneck >= 2 and r["factors"].relevance >= 2 and r["factors"].evidence >= 1]
    if not eligible:
        return []
    groups = {(r["mode"], r["execution_status"]) for r in eligible}
    if len(groups) != 1:
        raise ValueError("Rank alternatives separately by objective and execution status")
    eligible.sort(key=lambda r: (-r["utility"], r["path_id"]))
    best = eligible[0]
    selected = [{**best, "diversity_selection_score": best["utility"] / 100}]
    candidates = [r for r in eligible[1:] if r["utility"] >= best["utility"] - 15]
    while candidates and len(selected) < limit:
        scored = [(r["utility"] / 100 - Decimal(".20") * max(route_redundancy(r, chosen) for chosen in selected), r) for r in candidates]
        value, chosen = min(scored, key=lambda pair: (-pair[0], pair[1]["path_id"]))
        # Exact lineage/node/source copies are not meaningful alternatives.
        if all(route_redundancy(chosen, existing) < 1 for existing in selected):
            selected.append({**chosen, "diversity_selection_score": value})
        candidates.remove(chosen)
    return selected


def sensitivity_report(routes: list[dict]) -> dict:
    """Plausible ±5pt coefficient transfers; flags unstable first recommendations."""
    variants = (
        COEFFICIENTS,
        (Decimal(".35"), Decimal(".30"), Decimal(".20"), Decimal(".10"), Decimal(".05")),
        (Decimal(".45"), Decimal(".20"), Decimal(".20"), Decimal(".10"), Decimal(".05")),
        (Decimal(".40"), Decimal(".20"), Decimal(".25"), Decimal(".10"), Decimal(".05")),
        (Decimal(".40"), Decimal(".25"), Decimal(".15"), Decimal(".15"), Decimal(".05")),
    )
    runs = []
    for coefficients in variants:
        scored = [{**r, "utility": route_utility(r["factors"], r["hop_count"], coefficients=coefficients)} for r in routes]
        selected = select_alternatives(scored)
        runs.append({"coefficients": coefficients, "selected_path_ids": [r["path_id"] for r in selected]})
    firsts = {r["selected_path_ids"][0] if r["selected_path_ids"] else None for r in runs}
    return {"rubric_version": RUBRIC_VERSION, "first_recommendation_stable": len(firsts) <= 1, "variants": runs,
            "limitation": "Sensitivity to five explicit POC configurations is not business-outcome calibration."}
