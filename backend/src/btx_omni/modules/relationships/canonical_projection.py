"""One typed graph facade over persisted commercial records and reviewed sources."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from functools import lru_cache

from btx_omni.modules.commercial.ledger import KEYS
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.relationships.routes import (
    CanonicalRouteGraph,
    RouteEdge,
    RouteNode,
)
from btx_omni.persistence.commercial_import import BU_CROSSWALK, digest
from btx_omni.providers.research._catalog_support import document
from btx_omni.providers.research.enriched_evidence import public_sources
from btx_omni.providers.sample.environment import SampleEnvironment

SCOPE = "SAMPLE"
FACILITY_CROSSWALK = {"BTX-FAC-BU-ERA": "era-elk-grove", "BTX-FAC-BU-APM": "apm-rochester", "BTX-FAC-BU-A1J": "a1j-san-jose"}
EXPERIENCE_MODES = ("commercial_fit", "cross_account_experience")


@lru_cache(maxsize=1)
def relationship_catalog() -> dict:
    return document("enriched_relationship_catalog.json")


def project_route_graph(sample: SampleEnvironment, *, as_of: date, lookback_days: int = 365) -> tuple[CanonicalRouteGraph, dict]:
    catalog = relationship_catalog()
    sources = public_sources()
    nodes, aliases, edges, constraints = {}, {}, [], {}

    def node(kind, cid, label, *, account_id=None, alias=None):
        value = RouteNode(SCOPE, kind, cid, label, account_id)
        if value.id in nodes and nodes[value.id] != value:
            raise ValueError("Conflicting canonical graph node")
        nodes[value.id] = value
        for key in (cid, alias):
            if key:
                if key in aliases and aliases[key] != value.id:
                    raise ValueError("Ambiguous graph source identity")
                aliases[key] = value.id
        return value.id

    accounts = {a.id: a for a in sample.accounts}
    for account in sample.accounts:
        node("account", account.id, account.legal_name, account_id=account.id,
             alias=sample.commercial_ledgers.get(account.id, {}).get("account_id"))
    for unit in sample.business_units:
        node("business_unit", unit.id, unit.name, alias=next((sid for sid, cid in BU_CROSSWALK.items() if cid == unit.id), None))
    source_facilities = catalog["ontology"]["facilities"]
    existing_facilities = {f.id: f for f in sample.btx_facilities}
    for facility in source_facilities:
        fid = facility["facility_id"]
        canonical = FACILITY_CROSSWALK.get(fid, fid)
        if fid in FACILITY_CROSSWALK:
            existing = existing_facilities[canonical]
            if existing.business_unit_id != BU_CROSSWALK[facility["business_unit_id"]] or facility["location"] != f"{existing.city}, {existing.region}":
                raise ValueError("Facility crosswalk no longer matches scoped public identity")
        label = next(u.name for u in sample.business_units if u.id == BU_CROSSWALK[facility["business_unit_id"]]) + " · " + (facility["location"] or "location pending")
        node("btx_facility", canonical, label, alias=fid)
        observed = max(date.fromisoformat(sources[sid]["accessed_on"]) for sid in facility["source_ids"])
        edges.append(RouteEdge(f"structure:{fid}:bu", aliases[fid], aliases[facility["business_unit_id"]], "FACILITY_BU", tuple(facility["source_ids"]), (f"facility:{canonical}",), tuple(facility["source_ids"]), "SCOPED_PUBLIC_CLAIM", observed, facility_id=canonical))

    records_by_id = {}
    component_experience = {}
    temporal_limits = {}
    for aid, account in sample.commercial_ledgers.items():
        clock = min(as_of, date.fromisoformat(account["as_of"]))
        state = fulfillment_state(account, canonical_account_id=aid, revision=sample.commercial_revision or "unrecorded", as_of=clock)
        temporal_limits[aid] = state['temporal_limits']
        constraints.update({c["id"]: c for c in state["constraints"]})
        constraints_by_component = {}
        for line in state["lines"]:
            constraints_by_component.setdefault(line["component_id"], []).extend(c["id"] for c in line["constraints"])
        for collection, key in {**KEYS, "contacts": "contact_id", "supply_relationships": "relationship_id"}.items():
            for record in account[collection]:
                rid = record[key]
                records_by_id[rid] = record
                if collection not in {"programs", "components"}:
                    node("contact_candidate" if collection == "contacts" else "role_target" if collection == "role_targets" else collection, rid, record.get("full_name") or record.get("title") or record.get("label") or rid, account_id=aid)
        for program in account["programs"]:
            pid = program["program_id"]
            node("program", pid, program["name"], account_id=aid)
            edges.append(RouteEdge(f"structure:{aid}:{pid}", aliases[aid], aliases[pid], "ACCOUNT_PROGRAM", (pid,), (pid,), tuple(program.get("source_ids", [])), "POC_ASSUMPTION", clock, account_id=aid, program_id=pid, inverse_modes=EXPERIENCE_MODES))
        lines = {r["order_line_id"]: r for r in account["order_lines"]}
        for component in account["components"]:
            cid, pid = component["component_id"], component["program_id"]
            node("component_class", cid, component["name"], account_id=aid)
            edges.append(RouteEdge(f"structure:{pid}:{cid}", aliases[pid], aliases[cid], "PROGRAM_COMPONENT", (cid,), (cid,), tuple(component["source_ids"]), "POC_ASSUMPTION", clock, account_id=aid, component_id=cid, program_id=pid, inverse_modes=EXPERIENCE_MODES))
            edges.append(RouteEdge(f"structure:{aid}:{cid}", aliases[aid], aliases[cid], "ACCOUNT_COMPONENT", (cid,), (cid,), tuple(component["source_ids"]), "POC_ASSUMPTION", clock, account_id=aid, component_id=cid, program_id=pid, inverse_modes=EXPERIENCE_MODES))
            accepted = [r for r in account["revenue_events"] if lines[r["order_line_id"]]["component_id"] == cid and as_of - timedelta(days=lookback_days) <= date.fromisoformat(r["recognized_date"]) <= clock and r["quantity"] > 0]
            order_ids = tuple(sorted({lines[r["order_line_id"]]["order_id"] for r in accepted}))
            observed = max((date.fromisoformat(r["recognized_date"]) for r in accepted), default=None)
            component_experience[cid] = (order_ids, observed, tuple(sorted(r["revenue_event_id"] for r in accepted)), tuple(sorted(set(constraints_by_component.get(cid, [])))))
            if accepted:
                fid = component["btx_facility_id"]
                # Facility scope must agree with the accepted work, not just BU-level fit.
                scoped = [r for r in accepted if lines[r["order_line_id"]].get("btx_facility_id") == fid]
                if scoped:
                    scoped_orders = tuple(sorted({lines[r["order_line_id"]]["order_id"] for r in scoped}))
                    scoped_observed = max(date.fromisoformat(r["recognized_date"]) for r in scoped)
                    edges.append(RouteEdge(f"experience:{fid}:{cid}", aliases[fid], aliases[cid], "PRODUCED_ACCEPTED_COMPONENT", tuple(sorted(r["revenue_event_id"] for r in scoped)), tuple(f"accepted-order:{oid}" for oid in scoped_orders), ("AS-COMMERCIAL-V2",), "POC_SCENARIO_RECORD", scoped_observed, account_id=aid, component_id=cid, program_id=pid, facility_id=FACILITY_CROSSWALK.get(fid, fid), accepted_order_ids=scoped_orders, inverse_modes=EXPERIENCE_MODES, constraint_ids=component_experience[cid][3]))

    for aid, account in sample.commercial_ledgers.items():
        for row in account.get('route_evidence', []):
            if not (row.get('synthetic') is True and row.get('data_mode') == 'SAMPLE'):
                raise ValueError('Authored route evidence must remain explicitly synthetic.')
            if not all(eid in records_by_id for eid in row['evidence_ids']):
                raise ValueError('Unresolved synthetic route evidence')
            edges.append(RouteEdge(row['id'], aliases[row['source_facility_id']], aliases[row['target_facility_id']],
                'COORDINATED_HANDOFF', tuple(row['evidence_ids']), (row['id'],), (row['source_url'],), 'POC_SCENARIO_RECORD',
                date.fromisoformat(row['observed_on']), account_id=aid, component_id=row['component_id'],
                accepted_order_ids=tuple(row['accepted_order_ids'])))
    imported_seed_ids, pending_seed_ids = [], []
    for seed in catalog["edges"]:
        if seed["from_id"] not in aliases or seed["to_id"] not in aliases:
            pending_seed_ids.append(seed["edge_id"])
            continue
        evidence = tuple(seed["evidence_ids"])
        if any(eid not in records_by_id and eid not in sources for eid in evidence):
            raise ValueError("Seed relationship has unresolved evidence")
        source, target = aliases[seed["from_id"]], aliases[seed["to_id"]]
        aid = nodes[target].account_id or nodes[source].account_id
        observed = date.fromisoformat(seed["observed_on"]) if seed.get("observed_on") else max((date.fromisoformat(sources[eid]["accessed_on"]) for eid in evidence if eid in sources), default=None)
        modes = ("contact_candidates",) if seed["predicate"] == "PUBLISHED_ROLE_AT" else EXPERIENCE_MODES
        edge = RouteEdge(seed["edge_id"], source, target, seed["predicate"], evidence, (seed["edge_id"],), evidence, seed["truth_class"], observed,
                         account_id=aid, component_id=seed.get("component_id") or (seed["to_id"] if seed["to_id"].startswith("C2-") else None), program_id=seed.get("program_id"), inverse_modes=modes)
        if seed["predicate"] == "SCENARIO_SUPPLIER_FOR_COMPONENT":
            component = records_by_id[seed["component_id"]]
            if aliases[component["business_unit_id"]] != source or aliases[component["component_id"]] not in nodes or nodes[aliases[component["component_id"]]].account_id != aid:
                raise ValueError("Supplier assertion conflicts with canonical component/account/BU scope")
            order_ids, observed, accepted_ids, blocked = component_experience[seed["component_id"]]
            edge = replace(edge, accepted_order_ids=order_ids, observed_on=observed, evidence_ids=tuple(sorted(set(evidence + accepted_ids))),
                           lineage_groups=tuple(f"accepted-order:{oid}" for oid in order_ids) or edge.lineage_groups,
                           source_lineage=("AS-COMMERCIAL-V2",), truth_class="POC_SCENARIO_RECORD" if order_ids else "POC_ASSUMPTION", constraint_ids=blocked)
        edges.append(edge)
        imported_seed_ids.append(seed["edge_id"])
    from btx_omni.modules.relationships.record_projection import (
        project_record_references,
    )
    record_edges, record_metadata = project_record_references(sample, nodes, aliases)
    edges.extend(record_edges)
    revision = digest({"commercial_revision": sample.commercial_revision, "catalog": catalog, "projection": "BTX_CANONICAL_GRAPH_POC_3", "as_of": as_of.isoformat(), "lookback_days": lookback_days})
    graph = CanonicalRouteGraph(tuple(nodes.values()), tuple(edges), revision)
    return graph, {"constraints": constraints, "temporal_limits": temporal_limits, "seed_edge_count": len(imported_seed_ids),
                   "pending_seed_ids": pending_seed_ids, "canonical_node_count": len(nodes), "canonical_edge_count": len(graph.edges),
                   "record_projection": record_metadata,
                   "scope": "Single configured SAMPLE environment; no multi-tenant support is asserted.",
                   "account_names": {aid: accounts[aid].legal_name for aid in sample.commercial_ledgers}}
