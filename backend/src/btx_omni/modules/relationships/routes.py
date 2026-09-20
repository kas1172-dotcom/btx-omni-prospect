"""Typed, permission-scoped bounded simple-edge-path search over canonical facts."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from time import monotonic

from btx_omni.modules.relationships.rubric import (
    RUBRIC_VERSION,
    RouteFactors,
    route_utility,
    select_alternatives,
    sensitivity_report,
)

MODES = frozenset(("commercial_fit", "cross_account_experience", "contact_candidates", "documented_access"))
STRUCTURAL = frozenset(("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "FACILITY_BU", "ACCOUNT_COMPONENT"))
TEMPLATES = {
    "cross_account_experience": (
        ("SCENARIO_SUPPLIER_FOR_COMPONENT:inverse", "SCENARIO_SUPPLIER_FOR_COMPONENT"),
        ("ACCOUNT_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse", "FACILITY_BU", "SCENARIO_SUPPLIER_FOR_COMPONENT"),
        ("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse", "FACILITY_BU", "SCENARIO_SUPPLIER_FOR_COMPONENT"),
        ("ACCOUNT_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse", "PRODUCED_ACCEPTED_COMPONENT", "ACCOUNT_COMPONENT:inverse"),
        ("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse", "PRODUCED_ACCEPTED_COMPONENT", "PROGRAM_COMPONENT:inverse", "ACCOUNT_PROGRAM:inverse"),
    ),
    "commercial_fit": (
        ("ACCOUNT_COMPONENT", "PLAUSIBLE_CAPABILITY_FIT:inverse"),
        ("ACCOUNT_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse"),
        ("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "PLAUSIBLE_CAPABILITY_FIT:inverse"),
        ("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse"),
        ("ACCOUNT_PROGRAM", "PROGRAM_COMPONENT", "PRODUCED_ACCEPTED_COMPONENT:inverse", "COORDINATED_HANDOFF"),
    ),
    "contact_candidates": (("PUBLISHED_ROLE_AT:inverse",), ("WORKS_AT:inverse",)),
    "documented_access": (*tuple(("EXPLICIT_INTRODUCTION",) * n for n in range(1, 7)), ("WORKS_AT:inverse", "KNOWS:inverse")),
}


@dataclass(frozen=True)
class RouteNode:
    scope_id: str
    kind: str
    canonical_id: str
    label: str
    account_id: str | None = None
    resolved: bool = True
    contact_count: int | None = None
    senior_contact_count: int | None = None
    source_people: tuple[str, ...] = ()
    unvalidated: bool = False
    role_family: str | None = None
    seniority_tier: str | None = None
    profile_url: str | None = None
    raw_title: str | None = None
    provenance_label: str | None = None
    exported_on: date | None = None
    resolution_method: str | None = None

    @property
    def id(self) -> str:
        return f"{self.scope_id}:{self.kind}:{self.canonical_id}"


@dataclass(frozen=True)
class RouteEdge:
    id: str
    source: str
    target: str
    predicate: str
    evidence_ids: tuple[str, ...]
    lineage_groups: tuple[str, ...]
    source_lineage: tuple[str, ...]
    truth_class: str
    observed_on: date | None
    account_id: str | None = None
    component_id: str | None = None
    program_id: str | None = None
    facility_id: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    accepted_order_ids: tuple[str, ...] = ()
    inverse_modes: tuple[str, ...] = ()
    conflicting: bool = False
    constraint_ids: tuple[str, ...] = ()
    derivation_rule: str = "BTX_CANONICAL_GRAPH_POC_1"
    relevance_score: int | None = None


@dataclass(frozen=True)
class RouteQuery:
    scope_id: str
    source_id: str
    target_ids: frozenset[str]
    mode: str
    as_of: date
    authorized_account_ids: frozenset[str]
    source_component_id: str | None = None
    target_component_id: str | None = None
    max_depth: int = 4
    lookback_days: int = 365
    max_expansions: int = 50_000
    max_candidates: int = 5000
    deadline_seconds: float = .25

    def __post_init__(self):
        if self.mode not in MODES or not 1 <= self.max_depth <= 6 or not 1 <= self.max_expansions <= 50_000 or not 1 <= self.max_candidates <= 5000 or not 0 < self.deadline_seconds <= 5 or not 1 <= self.lookback_days <= 3650:
            raise ValueError("Invalid bounded relationship query")


class CanonicalRouteGraph:
    def __init__(self, nodes: tuple[RouteNode, ...], edges: tuple[RouteEdge, ...], revision: str):
        self.nodes = {n.id: n for n in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("Duplicate canonical node")
        self.edges: dict[str, RouteEdge] = {}
        self.adjacency = defaultdict(list)
        for edge in sorted(edges, key=lambda e: e.id):
            if edge.source not in self.nodes or edge.target not in self.nodes:
                raise ValueError("Unresolved edge endpoint")
            if self.nodes[edge.source].scope_id != self.nodes[edge.target].scope_id:
                raise ValueError("Cross-environment assertion rejected")
            previous = self.edges.get(edge.id)
            if previous:
                if previous != edge:
                    raise ValueError("Conflicting versions require canonical resolution")
                continue
            self.edges[edge.id] = edge
            self.adjacency[edge.source].append((edge, False))
            if edge.inverse_modes:
                self.adjacency[edge.target].append((edge, True))
        self.revision = revision

    def _node_allowed(self, node_id: str, query: RouteQuery) -> bool:
        node = self.nodes.get(node_id)
        return bool(node and node.resolved and node.scope_id == query.scope_id
                    and (node.account_id is None or node.account_id in query.authorized_account_ids)
                    and node.kind not in {"industry", "naics", "geography"})

    def _edge_allowed(self, edge: RouteEdge, inverse: bool, query: RouteQuery) -> bool:
        if inverse and query.mode not in edge.inverse_modes:
            return False
        if edge.conflicting or not edge.evidence_ids or not self._node_allowed(edge.source, query) or not self._node_allowed(edge.target, query):
            return False
        if edge.account_id and edge.account_id not in query.authorized_account_ids:
            return False
        if edge.valid_from and edge.valid_from > query.as_of or edge.valid_until and edge.valid_until < query.as_of:
            return False
        if edge.observed_on and edge.observed_on > query.as_of:
            return False
        source_account = self.nodes[query.source_id].account_id
        target_accounts = {self.nodes[t].account_id for t in query.target_ids if t in self.nodes}
        if query.source_component_id and edge.account_id == source_account and edge.predicate not in STRUCTURAL and edge.component_id != query.source_component_id:
            return False
        if query.target_component_id and edge.account_id in target_accounts and edge.account_id != source_account and edge.predicate not in STRUCTURAL and edge.component_id != query.target_component_id:
            return False
        if query.mode == "documented_access":
            imported_path_edge = edge.predicate in {"KNOWS", "WORKS_AT"} and edge.truth_class == "ANALYST_INFERENCE"
            if not imported_path_edge and (edge.predicate != "EXPLICIT_INTRODUCTION" or not edge.valid_until or not edge.observed_on):
                return False
        return not (edge.accepted_order_ids and (not edge.observed_on or edge.observed_on < query.as_of - timedelta(days=query.lookback_days)))

    @staticmethod
    def _factors(hops: tuple[tuple[RouteEdge, bool], ...], query: RouteQuery) -> tuple[RouteFactors, list[dict]]:
        substantive = [e for e, _ in hops if e.predicate not in STRUCTURAL]
        if not substantive:
            raise ValueError("Structural paths cannot manufacture relationship strength")
        rows = []
        for edge in substantive:
            strength = 3 if len(set(edge.accepted_order_ids)) >= 2 or edge.predicate == "EXPLICIT_INTRODUCTION" else 2 if edge.accepted_order_ids else 1
            if query.mode == "documented_access" and edge.predicate != "EXPLICIT_INTRODUCTION":
                strength = 0
            evidence = {"POC_SCENARIO_RECORD": 3, "SOURCED_PUBLIC_FACT": 3, "SCOPED_PUBLIC_CLAIM": 2, "ANALYST_INFERENCE": 1, "POC_ASSUMPTION": 1}.get(edge.truth_class, 0)
            tolerance = 90 if edge.predicate == "PUBLISHED_ROLE_AT" else query.lookback_days if edge.accepted_order_ids else 365
            age = (query.as_of - edge.observed_on).days if edge.observed_on else None
            freshness = 2 if edge.valid_until and edge.valid_until >= query.as_of else 2 if edge.accepted_order_ids and age is not None and 0 <= age <= 90 else 1 if age is not None and 0 <= age <= tolerance else 0
            required = ("identity", "scope", "evidence", "date")
            present = {"identity", "evidence"}
            if edge.component_id or edge.predicate in {"PUBLISHED_ROLE_AT", "EXPLICIT_INTRODUCTION"}:
                present.add("scope")
            if edge.observed_on:
                present.add("date")
            rows.append({"edge_id": edge.id, "B": strength, "E": evidence, "F": freshness,
                         "applicable_fields": required, "present_fields": tuple(sorted(present)),
                         "reason": f"{len(set(edge.accepted_order_ids))} distinct accepted orders support scoped experience." if edge.accepted_order_ids else "Published role candidate; no introduction is established." if edge.predicate == "PUBLISHED_ROLE_AT" else "Explicit introduction evidence is valid for the scoped query date." if edge.predicate == "EXPLICIT_INTRODUCTION" else "Traced fit inference requires technical review.",
                         "truth_class": edge.truth_class})
        coverage = Decimal(sum(len(r["present_fields"]) for r in rows)) / sum(len(r["applicable_fields"]) for r in rows)
        imported_relevance = [edge.relevance_score for edge in substantive if edge.relevance_score is not None]
        relevance = min(imported_relevance) if imported_relevance else 3 if query.source_component_id and all(e.component_id in {query.source_component_id, query.target_component_id} for e in substantive) else 2
        return RouteFactors(min(r["B"] for r in rows), relevance, min(r["E"] for r in rows), min(r["F"] for r in rows), coverage), rows

    def search(self, query: RouteQuery, *, cancelled: Callable[[], bool] = lambda: False) -> dict:
        if not self._node_allowed(query.source_id, query) or any(not self._node_allowed(t, query) for t in query.target_ids):
            raise PermissionError("Unresolved or unauthorized relationship scope")
        templates = TEMPLATES[query.mode]
        paths, examined, stop_reason = [], 0, None
        deadline = monotonic() + query.deadline_seconds
        # An explicitly resolved empty target set is a complete no-path result,
        # not permission to enumerate all nodes. Authorization still runs above.
        stack = [(query.source_id, (), (query.source_id,), ())] if query.target_ids else []
        while stack and stop_reason is None:
            current, hops, nodes, sequence = stack.pop()
            if len(hops) >= query.max_depth:
                continue
            children = []
            for edge, inverse in self.adjacency.get(current, ()):
                if cancelled():
                    stop_reason = "CANCELLED"
                    break
                if monotonic() >= deadline:
                    stop_reason = "DEADLINE"
                    break
                if examined >= query.max_expansions:
                    stop_reason = "EXPANSION_LIMIT"
                    break
                examined += 1
                next_node = edge.source if inverse else edge.target
                token = edge.predicate + (":inverse" if inverse else "")
                next_sequence = (*sequence, token)
                if next_node in nodes or not any(t[:len(next_sequence)] == next_sequence for t in templates) or not self._edge_allowed(edge, inverse, query):
                    continue
                next_hops, next_nodes = (*hops, (edge, inverse)), (*nodes, next_node)
                if next_node in query.target_ids and next_sequence in templates:
                    factors, reasons = self._factors(next_hops, query)
                    path_id = "path:" + sha256("|".join(e.id + (":inverse" if inv else "") for e, inv in next_hops).encode()).hexdigest()[:32]
                    constraints = sorted({cid for e, _ in next_hops for cid in e.constraint_ids})
                    paths.append({"path_id": path_id, "node_ids": next_nodes, "edge_ids": tuple(e.id for e, _ in next_hops), "inverse_steps": tuple(inv for _, inv in next_hops),
                                  "hop_count": len(next_hops), "mode": query.mode, "as_of": query.as_of,
                                  "factors": factors, "factor_reasons": reasons, "utility": route_utility(factors, len(next_hops)),
                                  "eligible": factors.evidence >= 1,
                                  "execution_status": "BLOCKED" if constraints else "NEEDS_CHECK",
                                  "constraint_ids": constraints,
                                  "edge_lineage": sorted({group for e, _ in next_hops for group in e.lineage_groups}),
                                  "source_lineage": sorted({group for e, _ in next_hops for group in e.source_lineage}),
                                  "evidence_ids": sorted({eid for e, _ in next_hops for eid in e.evidence_ids}),
                                  "rubric_version": RUBRIC_VERSION})
                    if len(paths) >= query.max_candidates:
                        stop_reason = "CANDIDATE_LIMIT"
                        break
                children.append((next_node, next_hops, next_nodes, next_sequence))
            stack.extend(reversed(children))
        paths.sort(key=lambda p: (-p["utility"], p["path_id"]))
        groups = {}
        for status in ("FEASIBLE", "NEEDS_CHECK", "BLOCKED"):
            members = [p for p in paths if p["execution_status"] == status]
            groups[status] = {"routes": select_alternatives(members), "sensitivity": sensitivity_report(members)}
        candidates = [p for p in paths if not p["eligible"] or p["factors"].bottleneck < 2 or p["factors"].relevance < 2]
        return {"groups": groups, "research_candidates": candidates[:3], "evaluated_routes": paths[:25], "additional_route_count": max(0, len(paths) - 25), "candidate_count": len(paths),
                "search_complete": stop_reason is None, "searched_depth": query.max_depth,
                "examined_count": examined, "stop_reason": stop_reason,
                "eligible_graph_revision": self.revision, "scope": {"source_id": query.source_id, "target_ids": sorted(query.target_ids), "as_of": query.as_of, "lookback_days": query.lookback_days, "source_component_id": query.source_component_id, "target_component_id": query.target_component_id},
                "rubric_version": RUBRIC_VERSION, "mode": query.mode,
                "result_label": "Ranked eligible routes" if stop_reason is None else "Best paths found; search incomplete"}
