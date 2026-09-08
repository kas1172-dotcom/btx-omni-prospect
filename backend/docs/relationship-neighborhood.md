# Graph context versus commercial routes

The existing relationship query uses `BTX_GRAPH_NEIGHBORHOOD_1` to choose context before SVG layout. It does not modify `BTX_RELATIONSHIP_POC_1` utilities, eligibility or alternative selection. Context-only connectivity must not be described as a recommended introduction or supply route.

Default neighborhood: two permitted assertion traversals from the selected account. Up to eight explicit `expanded_node_ids` add one-hop context; each anchor needs an authorized, temporally suitable connection within six edges. This connectivity check is not strongest-path ranking. A default four-edge route query remains four-edge even when its context is expanded. Generic industry/geography hubs are excluded by the shared graph gates.

Expansion memberships and route memberships are separate arrays on each canonical edge. An open expansion retains its own connecting assertions even after another expansion closes. Parallel predicates retain distinct IDs. Context pages retain the complete selected route and connection paths, obey node/edge budgets and report hidden counts. An explicit wider context budget can expose connections that do not fit the initial viewport.

The independent context scan is capped at 20,000 examined edges and a 100ms measured server deadline. `context_complete`/`context_stop_reason` are separate from route `search_complete`/`stop_reason`. These are provisional POC safeguards, not scale guarantees. `expected_graph_revision` rejects outdated context operations; refresh explicitly resets the selection when the evidence has changed. No shared private-response cache is introduced.

The current SVG preserves canonical-ID positions across expansion/pages within the graph-view context. Explicit Fit resets placement. Desktop starts at24nodes/40edges; mobile12/20. Ordered routes and a full visible-assertion text equivalent retain evidence access; touch/keyboard expansion, paging, edge selection and non-drag pan controls are available. Full refreshed-session position persistence, complete commercial-history projection and legacy graph convergence remain separate qualification items.
