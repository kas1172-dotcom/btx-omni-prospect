"""Bounded context selection, independent of route ranking and layout."""
from collections import defaultdict, deque
from dataclasses import asdict
from time import monotonic

from btx_omni.modules.relationships.record_projection import MODES, PREDICATES
from btx_omni.modules.relationships.routes import TEMPLATES

VIEW_VERSION = 'BTX_GRAPH_NEIGHBORHOOD_1'


def project_neighborhood(graph, query, routes, selected, *, expanded_node_ids=(), page=0,
                         node_budget=24, edge_budget=40, max_examined=20_000, deadline_seconds=.1,
                         include_record_context=False):
    if not 7 <= node_budget <= 80 or not 6 <= edge_budget <= 160 or not 0 <= page <= 200 or len(expanded_node_ids) > 8:
        raise ValueError('Invalid bounded graph viewport request.')
    if not graph._node_allowed(query.source_id, query):
        raise PermissionError('Graph source is outside the authorized scope.')
    start = monotonic()
    allowed_tokens = {token for template in TEMPLATES[query.mode] for token in template}
    membership, distances = defaultdict(set), {}
    connectors = {}
    examined, stop_reason = 0, None

    def eligible(edge, inverse):
        token = edge.predicate + (':inverse' if inverse else '')
        record_context = include_record_context and query.mode in MODES and edge.predicate in PREDICATES
        if (token not in allowed_tokens and not record_context) or not graph._edge_allowed(edge, inverse, query):
            return False
        for node_id in (edge.source, edge.target):
            node = graph.nodes[node_id]
            if node.kind == 'component_class':
                source_account = graph.nodes[query.source_id].account_id
                if node.account_id == source_account and query.source_component_id and node.canonical_id != query.source_component_id:
                    return False
                if node.account_id != source_account and query.target_component_id and node.canonical_id != query.target_component_id:
                    return False
        return True

    def budget():
        nonlocal examined, stop_reason
        if examined >= max_examined or monotonic() - start >= deadline_seconds:
            stop_reason = 'EXPANSION_LIMIT' if examined >= max_examined else 'DEADLINE'
            return False
        examined += 1
        return True

    def explore(anchor, depth, owner, prefix=()):
        nonlocal examined, stop_reason
        queue, visited = deque([(anchor, 0, prefix)]), {anchor}
        while queue and not stop_reason:
            current, level, path = queue.popleft()
            if level >= depth:
                continue
            for edge, inverse in graph.adjacency.get(current, ()):
                if not budget():
                    break
                if not eligible(edge, inverse):
                    continue
                target = edge.source if inverse else edge.target
                membership[edge.id].add(owner)
                distances[edge.id] = min(distances.get(edge.id, 99), level + 1)
                chain = tuple(dict.fromkeys((*path, edge.id)))
                if edge.id not in connectors or (len(chain), chain) < (len(connectors[edge.id]), connectors[edge.id]):
                    connectors[edge.id] = chain
                if target not in visited:
                    visited.add(target)
                    queue.append((target, level + 1, chain))
        return visited

    explore(query.source_id, 2, 'neighborhood:source')
    pinned_nodes = set(selected['node_ids'] if selected else (query.source_id,))
    pinned_edges = set(selected['edge_ids'] if selected else ())
    accepted = []
    for anchor in sorted(set(expanded_node_ids)):
        if not graph._node_allowed(anchor, query):
            raise PermissionError('Expansion anchor is outside the authorized scope.')
        # A bounded connectivity path is context, NOT a strongest-route search.
        # Attribute its edges to this expansion so collapsing another expansion
        # cannot remove the only connection needed by this still-open anchor.
        queue, visited, connection = deque([(query.source_id, ())]), {query.source_id}, None
        while queue and not stop_reason:
            current, path = queue.popleft()
            if current == anchor:
                connection = path
                break
            if len(path) >= 6:
                continue
            for edge, inverse in graph.adjacency.get(current, ()):
                if not budget():
                    break
                target = edge.source if inverse else edge.target
                if target not in visited and eligible(edge, inverse):
                    visited.add(target)
                    queue.append((target, (*path, edge.id)))
        if stop_reason:
            break
        if connection is None:
            raise ValueError('Expansion anchor has no permitted connection within the six-edge context bound.')
        owner = 'expansion:' + anchor
        for index, eid in enumerate(connection):
            membership[eid].add(owner)
            distances[eid] = min(distances.get(eid, 99), index + 1)
            chain = connection[:index + 1]
            if eid not in connectors or (len(chain), chain) < (len(connectors[eid]), connectors[eid]):
                connectors[eid] = chain
        explore(anchor, 1, owner, connection)
        accepted.append(anchor)
    route_membership = defaultdict(set)
    for route in routes:
        for eid in route['edge_ids']:
            route_membership[eid].add(route['path_id'])
    for eid in pinned_edges:
        membership[eid].add('selected:' + selected['path_id'])

    # Pack edge-distinct context pages. Selected path is complete on EVERY page;
    # endpoints and edge IDs are never cloned to make a tree layout.
    ordered = sorted(set(membership) - pinned_edges,
                     key=lambda eid: (not any(owner.startswith('expansion:') for owner in membership[eid]),
                                      not (include_record_context and graph.edges[eid].predicate in PREDICATES),
                                      not bool(route_membership[eid]), distances[eid], eid))
    pages = []
    current_nodes, current_edges = set(pinned_nodes), set(pinned_edges)
    for eid in ordered:
        group = set(connectors[eid])
        endpoints = {nid for key in group for nid in (graph.edges[key].source, graph.edges[key].target)}
        if len(pinned_nodes | endpoints) > node_budget or len(pinned_edges | group) > edge_budget:
            continue
        if len(current_nodes | endpoints) > node_budget or len(current_edges | group) > edge_budget:
            pages.append((current_nodes, current_edges))
            current_nodes, current_edges = set(pinned_nodes), set(pinned_edges)
        # At the smallest legal viewport a six-edge selected route can consume
        # every slot. Return an honest hidden count rather than violate budgets.
        if len(current_nodes | endpoints) <= node_budget and len(current_edges | group) <= edge_budget:
            current_nodes.update(endpoints)
            current_edges.update(group)
    pages.append((current_nodes, current_edges))
    pages = [item for i, item in enumerate(pages) if i == 0 or item != pages[i - 1]]
    if page >= len(pages):
        raise ValueError('Graph context page changed; return to the first page.')
    visible, visible_edges = pages[page]
    return {'nodes': [{**asdict(graph.nodes[nid]), 'id': nid} for nid in sorted(visible)],
            'edges': [{**asdict(graph.edges[eid]), 'path_ids': sorted(route_membership[eid]),
                       'expansion_owners': sorted(membership[eid])} for eid in sorted(visible_edges)],
            'selected_path_id': selected['path_id'] if selected else None,
            'node_budget': node_budget, 'edge_budget': edge_budget,
            'additional_route_nodes': len({nid for r in routes for nid in r['node_ids']} - visible),
            'view_version': VIEW_VERSION, 'neighborhood_depth': 2, 'expanded_node_ids': sorted(accepted),
            'context_page': page, 'page_count': len(pages), 'context_edge_count': len(membership),
            'hidden_context_edges': len(set(membership) - visible_edges),
            'context_complete': stop_reason is None, 'context_stop_reason': stop_reason,
            'context_examined_count': examined, 'selection_elapsed_ms': round((monotonic() - start) * 1000, 3),
            'context_authority': 'Context-only exploration; only ranked routes establish the declared commercial rubric.'}
