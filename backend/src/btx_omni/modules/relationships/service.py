"""Bounded, evidence-preserving traversal over typed canonical relationships."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from hashlib import sha256
from time import monotonic

from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import EvidenceState
from btx_omni.providers.sample.environment import SampleEnvironment


@dataclass(frozen=True, order=True)
class RelationshipEntity:
    kind: str
    id: str
    name: str


@dataclass(frozen=True)
class RelationshipHop:
    from_entity: RelationshipEntity
    relationship_type: str
    to_entity: RelationshipEntity
    evidence_state: EvidenceState
    provenance: Provenance | None
    source_ids: tuple[str, ...] = ()
    narrative: str | None = None
    derived: bool = False
    presentation_state: str = "unusable"
    assertion_id: str = ""
    inverse: bool = False


def presentation_state(evidence: EvidenceState) -> str:
    """Derived UI label; canonical evidence_state remains authoritative."""
    return {
        EvidenceState.CONFIRMED: "validated",
        EvidenceState.INFERRED: "needs_validation",
        EvidenceState.MISSING: "unusable",
        EvidenceState.CONFLICTING: "unusable",
    }[evidence]


def _hop_presentation_state(evidence: EvidenceState, source_ids: tuple[str, ...], derived: bool) -> str:
    if evidence is EvidenceState.CONFIRMED and not derived and not source_ids:
        return "needs_validation"
    return presentation_state(evidence)


def _path_presentation_state(hops: tuple[RelationshipHop, ...], evidence: EvidenceState) -> str:
    # A legacy edge can carry a governed record provenance without an attached
    # catalog source ID. Preserve the fact, but do not render it as a validated
    # seller path until research supplies the missing source reference.
    if evidence is EvidenceState.CONFIRMED and any(not hop.derived and not hop.source_ids for hop in hops):
        return "needs_validation"
    return presentation_state(evidence)


def _combined_evidence(states: tuple[EvidenceState, ...]) -> EvidenceState:
    order = {EvidenceState.CONFIRMED: 3, EvidenceState.INFERRED: 2, EvidenceState.MISSING: 1, EvidenceState.CONFLICTING: 0}
    return min(states, key=lambda state: order[state])


class RelationshipIntelligenceService:
    """Logical graph facade; it traverses canonical records and adds no graph rows."""

    def __init__(self, sample: SampleEnvironment) -> None:
        self.sample = sample
        self.entities = self._entities()
        self.adjacency: dict[RelationshipEntity, list[RelationshipHop]] = defaultdict(list)
        seen_assertions = set()
        for hop in self._logical_hops():
            membership = (hop.assertion_id, hop.inverse)
            if membership in seen_assertions:
                continue
            seen_assertions.add(membership)
            self.adjacency[hop.from_entity].append(hop)
        for hops in self.adjacency.values():
            hops.sort(key=lambda hop: (hop.relationship_type, hop.to_entity.kind, hop.to_entity.id, hop.assertion_id, hop.inverse))

    def _entities(self) -> dict[tuple[str, str], RelationshipEntity]:
        entities: dict[tuple[str, str], RelationshipEntity] = {}
        def add(kind: str, id: str, name: str) -> None: entities[(kind, id)] = RelationshipEntity(kind, id, name)
        for item in self.sample.accounts: add("account", item.id, item.legal_name)
        for item in self.sample.programs: add("program", item.id, item.name)
        for item in self.sample.component_classes: add("component_class", item.id, item.name)
        for item in self.sample.business_units: add("business_unit", item.id, item.name)
        for item in self.sample.capabilities: add("capability", item.id, item.name)
        for item in self.sample.public_facilities: add("facility", item.id, item.name)
        for item in self.sample.crm_contacts: add("contact", item.id, item.role_family)
        for item in self.sample.quotes: add("quote", item.id, item.id)
        for item in self.sample.orders: add("order", item.id, item.id)
        for item in self.sample.commercial_contexts: add("commercial_context", f"{item.account_id}:{item.business_unit}", item.business_unit)
        return entities

    def _entity(self, kind: str, id: str) -> RelationshipEntity:
        return self.entities[(kind, id)]

    def ranked_routes(self, query, *, selected_path_id: str | None = None, node_budget: int = 24, edge_budget: int = 40,
                      expanded_node_ids=(), context_page=0, expected_graph_revision=None, include_record_context=False) -> dict:
        """Commercial query and renderer projection reuse this canonical owner."""
        from btx_omni.modules.relationships.canonical_projection import (
            project_route_graph,
        )
        graph, metadata = project_route_graph(self.sample, as_of=query.as_of, lookback_days=query.lookback_days)
        metadata['record_projection']['unresolved_references'] = [item for item in metadata['record_projection']['unresolved_references']
                                                               if item['account_id'] in query.authorized_account_ids]
        if expected_graph_revision and graph.revision != expected_graph_revision:
            raise ValueError('Graph evidence changed; refresh before expanding or selecting context.')
        result = graph.search(query)
        recommendations = [r for group in result["groups"].values() for r in group["routes"]]
        routes = result["evaluated_routes"]
        for route in recommendations:
            if not any(item["path_id"] == route["path_id"] for item in routes):
                routes.append(route)
        result["additional_route_count"] = max(0, result["candidate_count"] - len(routes))
        selected = next((r for r in routes if r["path_id"] == selected_path_id), None) if selected_path_id else next(iter(recommendations or routes), None)
        if selected_path_id and selected is None:
            raise ValueError("Selected path is not present in this query revision")
        components = {c["component_id"]: {"id": c["component_id"], "label": c["name"], "account_id": aid, "facility_id": c.get("btx_facility_id"), "business_unit_id": c["business_unit_id"]} for aid, ledger in self.sample.commercial_ledgers.items() for c in ledger["components"]}
        for route in [*routes, *recommendations, *result["research_candidates"]]:
            route["steps"] = [{**asdict(graph.nodes[nid]), "id": nid} for nid in route["node_ids"]]
            route['assertions'] = [{'id': eid, 'predicate': graph.edges[eid].predicate,
                                    'inverse': inverse, 'truth_class': graph.edges[eid].truth_class}
                                   for eid, inverse in zip(route['edge_ids'], route['inverse_steps'], strict=True)]
            route["component_context"] = [components[cid] for cid in sorted({graph.edges[eid].component_id for eid in route["edge_ids"] if graph.edges[eid].component_id in components})]
            route["constraints"] = [metadata["constraints"][cid] for cid in route["constraint_ids"]]
            route["next_action"] = "Review recovery and feasibility constraints before making a commitment." if route["constraint_ids"] else "Review transferable experience and technical qualification; capability alone does not establish capacity." if query.mode != "contact_candidates" else "Verify the published role and identify the operational buyer; no introduction is established."
        from btx_omni.modules.relationships.neighborhood import project_neighborhood
        view = project_neighborhood(graph, query, routes, selected, expanded_node_ids=expanded_node_ids,
                                    page=context_page, node_budget=node_budget, edge_budget=edge_budget,
                                    include_record_context=include_record_context)
        return {**result, "graph": view,
                "temporal_limits": {aid: value for aid, value in metadata['temporal_limits'].items() if aid in query.authorized_account_ids},
                "projection_counts": {k: v for k, v in metadata.items() if k not in {"constraints", "account_names", "temporal_limits"}},
                "commercial_as_of": sorted({a["as_of"] for a in self.sample.commercial_ledgers.values()})}

    def _add(self, result: list[RelationshipHop], source: RelationshipEntity, relationship_type: str, target: RelationshipEntity, evidence_state: EvidenceState, provenance: Provenance | None, *, source_ids: tuple[str, ...] = (), narrative: str | None = None, derived: bool = True, reverse_type: str | None = None) -> None:
        label = _hop_presentation_state(evidence_state, source_ids, derived)
        identity = repr((source.kind, source.id, relationship_type, target.kind, target.id, provenance.source_system if provenance else None, provenance.source_record_id if provenance else None, tuple(sorted(source_ids))))
        assertion_id = "rel:" + sha256(identity.encode()).hexdigest()[:32]
        result.append(RelationshipHop(source, relationship_type, target, evidence_state, provenance, source_ids, narrative, derived, label, assertion_id, False))
        if reverse_type:
            result.append(RelationshipHop(target, reverse_type, source, evidence_state, provenance, source_ids, narrative, derived, label, assertion_id, True))

    def _logical_hops(self) -> tuple[RelationshipHop, ...]:
        result: list[RelationshipHop] = []
        for edge in self.sample.relationship_edges:
            self._add(result, self._entity("account", edge.from_account_id), edge.edge_type, self._entity("account", edge.to_account_id), edge.evidence_state, edge.provenance, source_ids=edge.source_ids, narrative=edge.narrative, derived=False, reverse_type=f"{edge.edge_type}_REVERSE")
        for facility in self.sample.public_facilities:
            self._add(result, self._entity("account", facility.account_id), "OPERATES", self._entity("facility", facility.id), EvidenceState.CONFIRMED, next(item.provenance for item in self.sample.accounts if item.id == facility.account_id), narrative="Publicly researched facility.", reverse_type="OPERATED_BY")
        for contact in self.sample.crm_contacts:
            if contact.account_id:
                self._add(result, self._entity("account", contact.account_id), "HAS_CONTACT", self._entity("contact", contact.id), contact.provenance.evidence_state, contact.provenance, narrative="SAMPLE CRM contact association.", reverse_type="CONTACT_FOR")
        for context in self.sample.commercial_contexts:
            account = self._entity("account", context.account_id); context_entity = self._entity("commercial_context", f"{context.account_id}:{context.business_unit}")
            self._add(result, account, "HAS_COMMERCIAL_CONTEXT", context_entity, context.provenance.evidence_state, context.provenance, reverse_type="COMMERCIAL_CONTEXT_FOR")
            self._add(result, account, "CUSTOMER_OF", self._entity("business_unit", context.business_unit), context.provenance.evidence_state, context.provenance, narrative="SAMPLE commercial context.", reverse_type="HAS_CUSTOMER")
        for quote in self.sample.quotes:
            account = self._entity("account", quote.account_id); quote_entity = self._entity("quote", quote.id)
            self._add(result, account, "QUOTED_WITH", quote_entity, quote.provenance.evidence_state, quote.provenance, reverse_type="QUOTE_FOR")
            for unit_id in quote.business_unit_ids or (quote.business_unit,):
                self._add(result, account, "QUOTED_WITH", self._entity("business_unit", unit_id), quote.provenance.evidence_state, quote.provenance, narrative="Scoped quote context; not proof of accepted work.", reverse_type="HAS_QUOTE")
            if quote.program_id: self._add(result, quote_entity, "QUOTED_PROGRAM_CONTEXT", self._entity("program", quote.program_id), EvidenceState.INFERRED, quote.provenance, reverse_type="HAS_QUOTE_CONTEXT")
            for component_id in quote.component_class_ids:
                self._add(result, quote_entity, "QUOTED_COMPONENT", self._entity("component_class", component_id), quote.provenance.evidence_state, quote.provenance, reverse_type="COMPONENT_QUOTED_ON")
        for order in self.sample.orders:
            account = self._entity("account", order.account_id); order_entity = self._entity("order", order.id)
            self._add(result, account, "ORDERED_WITH", order_entity, order.provenance.evidence_state, order.provenance, reverse_type="ORDER_FOR")
            self._add(result, account, "PARTICIPATES_IN", self._entity("program", order.program_id), order.provenance.evidence_state, order.provenance, reverse_type="HAS_PARTICIPANT")
            self._add(result, self._entity("program", order.program_id), "REQUIRES_COMPONENT_CLASS", self._entity("component_class", order.component_class_id), order.provenance.evidence_state, order.provenance, reverse_type="REQUIRED_BY_PROGRAM")
        for program in self.sample.programs:
            if program.account_id: self._add(result, self._entity("account", program.account_id), "RELATED_TO_PROGRAM", self._entity("program", program.id), program.evidence_state, program.provenance, reverse_type="PROGRAM_FOR")
        for component in self.sample.component_classes:
            for unit_id in component.business_unit_ids:
                self._add(result, self._entity("component_class", component.id), "CAPABILITY_MATCH", self._entity("business_unit", unit_id), component.evidence_state, component.provenance, reverse_type="MATCHES_COMPONENT_CLASS")
        for capability in self.sample.capabilities:
            for unit_id in capability.business_units:
                self._add(result, self._entity("business_unit", unit_id), "HAS_CAPABILITY", self._entity("capability", capability.id), capability.provenance.evidence_state if capability.provenance else EvidenceState.MISSING, capability.provenance, reverse_type="CAPABILITY_OF")
        return tuple(result)

    def account_relationships(self, account_id: str, *, depth: int = 2, max_paths: int = 5000, max_expansions: int = 50_000, deadline_seconds: float = 1.0) -> dict[str, object]:
        source = self.entities.get(("account", account_id))
        if source is None: raise KeyError(account_id)
        if not 1 <= depth <= 6 or not 1 <= max_paths <= 5000 or not 1 <= max_expansions <= 50_000 or not 0 < deadline_seconds <= 5:
            raise ValueError("Relationship search exceeds configured POC bounds")
        paths, path_ids, queue = [], set(), deque([(source, (), frozenset((source,)))])
        examined, stop_reason = 0, None
        deadline = monotonic() + deadline_seconds
        while queue and stop_reason is None:
            current, hops, visited = queue.popleft()
            if len(hops) >= depth: continue
            for hop in self.adjacency.get(current, ()):
                if monotonic() >= deadline:
                    stop_reason = "DEADLINE"
                    break
                if examined >= max_expansions:
                    stop_reason = "EXPANSION_LIMIT"
                    break
                examined += 1
                if hop.to_entity in visited:
                    continue
                next_hops = (*hops, hop)
                evidence = _combined_evidence(tuple(item.evidence_state for item in next_hops))
                path_id = "|".join(f"{item.assertion_id}:{'inverse' if item.inverse else 'forward'}" for item in next_hops)
                if path_id not in path_ids:
                    path_ids.add(path_id)
                    paths.append({"path_id": path_id, "source_entity": source, "target_entity": hop.to_entity, "hops": next_hops, "overall_evidence_state": evidence, "presentation_state": _path_presentation_state(next_hops, evidence), "narrative": next((item.narrative for item in reversed(next_hops) if item.narrative), None)})
                    if len(paths) >= max_paths:
                        stop_reason = "CANDIDATE_LIMIT"
                        break
                queue.append((hop.to_entity, next_hops, visited | {hop.to_entity}))
        paths.sort(key=lambda item: (len(item["hops"]), item["target_entity"].kind, item["target_entity"].id, item["path_id"]))
        return {"account": source, "max_depth": depth, "truncated": stop_reason is not None,
                "search_complete": stop_reason is None, "searched_depth": depth,
                "examined_count": examined, "stop_reason": stop_reason,
                "scope": "CONTEXT_NEIGHBORHOOD_NOT_ACTIONABLE_ROUTE_RANKING",
                "direct_relationships": [item for item in paths if len(item["hops"]) == 1], "paths": paths}
