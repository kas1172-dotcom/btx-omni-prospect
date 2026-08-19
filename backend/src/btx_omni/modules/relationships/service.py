"""Bounded, evidence-preserving traversal over typed canonical relationships."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

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


def presentation_state(evidence: EvidenceState) -> str:
    """Derived UI label; canonical evidence_state remains authoritative."""
    return {
        EvidenceState.CONFIRMED: "validated",
        EvidenceState.INFERRED: "needs_validation",
        EvidenceState.MISSING: "unusable",
        EvidenceState.CONFLICTING: "unusable",
    }[evidence]


def _combined_evidence(states: tuple[EvidenceState, ...]) -> EvidenceState:
    order = {EvidenceState.CONFIRMED: 3, EvidenceState.INFERRED: 2, EvidenceState.MISSING: 1, EvidenceState.CONFLICTING: 0}
    return min(states, key=lambda state: order[state])


class RelationshipIntelligenceService:
    """Logical graph facade; it traverses canonical records and adds no graph rows."""

    def __init__(self, sample: SampleEnvironment) -> None:
        self.sample = sample
        self.entities = self._entities()
        self.adjacency: dict[RelationshipEntity, list[RelationshipHop]] = defaultdict(list)
        for hop in self._logical_hops():
            self.adjacency[hop.from_entity].append(hop)
        for hops in self.adjacency.values():
            hops.sort(key=lambda hop: (hop.relationship_type, hop.to_entity.kind, hop.to_entity.id, hop.narrative or ""))

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

    def _add(self, result: list[RelationshipHop], source: RelationshipEntity, relationship_type: str, target: RelationshipEntity, evidence_state: EvidenceState, provenance: Provenance | None, *, source_ids: tuple[str, ...] = (), narrative: str | None = None, derived: bool = True, reverse_type: str | None = None) -> None:
        result.append(RelationshipHop(source, relationship_type, target, evidence_state, provenance, source_ids, narrative, derived))
        if reverse_type:
            result.append(RelationshipHop(target, reverse_type, source, evidence_state, provenance, source_ids, narrative, derived))

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
            self._add(result, account, "QUOTED_WITH", self._entity("business_unit", quote.business_unit), quote.provenance.evidence_state, quote.provenance, narrative="SAMPLE Paperless-like quote.", reverse_type="HAS_QUOTE")
            if quote.program_id: self._add(result, account, "PARTICIPATES_IN", self._entity("program", quote.program_id), quote.provenance.evidence_state, quote.provenance, reverse_type="HAS_PARTICIPANT")
            for component_id in quote.component_class_ids:
                if quote.program_id: self._add(result, self._entity("program", quote.program_id), "REQUIRES_COMPONENT_CLASS", self._entity("component_class", component_id), quote.provenance.evidence_state, quote.provenance, reverse_type="REQUIRED_BY_PROGRAM")
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

    def account_relationships(self, account_id: str, *, depth: int = 2, max_paths: int = 500) -> dict[str, object]:
        source = self.entities.get(("account", account_id))
        if source is None: raise KeyError(account_id)
        paths, path_ids, queue, visited = [], set(), deque([(source, ())]), {source}
        while queue and len(paths) < max_paths:
            current, hops = queue.popleft()
            if len(hops) >= depth: continue
            for hop in self.adjacency.get(current, ()):
                if len(paths) >= max_paths:
                    break
                already_seen = hop.to_entity in visited
                # Preserve all direct evidence for an account, but only retain
                # one shortest continuation to a previously visited node.
                if hops and already_seen and hop.relationship_type != "CAPABILITY_MATCH":
                    continue
                next_hops = (*hops, hop)
                evidence = _combined_evidence(tuple(item.evidence_state for item in next_hops))
                path_id = "|".join(f"{item.from_entity.kind}:{item.from_entity.id}:{item.relationship_type}:{item.to_entity.kind}:{item.to_entity.id}" for item in next_hops)
                if path_id not in path_ids:
                    path_ids.add(path_id)
                    paths.append({"path_id": path_id, "source_entity": source, "target_entity": hop.to_entity, "hops": next_hops, "overall_evidence_state": evidence, "presentation_state": presentation_state(evidence), "narrative": next((item.narrative for item in reversed(next_hops) if item.narrative), None)})
                if not already_seen:
                    visited.add(hop.to_entity); queue.append((hop.to_entity, next_hops))
        paths.sort(key=lambda item: (len(item["hops"]), item["target_entity"].kind, item["target_entity"].id, item["path_id"]))
        return {"account": source, "max_depth": depth, "truncated": bool(queue), "direct_relationships": [item for item in paths if len(item["hops"]) == 1], "paths": paths}
