# Relationship POC contract

Owner: `modules/relationships`; rubric `BTX_RELATIONSHIP_POC_1`. This is provisional product configuration, not Jamie-approved calibration, a probability, PWIN or Account Attractiveness. Layout never participates in ranking.

## Search and authority

The canonical facade uses the configured SAMPLE namespace and existing records. Authentication precedes the query; this does not assert multi-tenant infrastructure. Target accounts/facilities/contacts are resolved before search. Predicate templates are explicit in `routes.TEMPLATES`; structural account/program/component/facility links preserve meaning but do not supply bottleneck strength. A quote alone does not establish participation or accepted work. Generic industry/geography nodes cannot bridge actionable routes. Reverse traversal retains the original assertion ID and direction.

The default query permits four assertion edges, explicit deeper search six. Stable edge-distinct DFS excludes repeated canonical nodes with path-local visitation. Limits: 50,000 examined expansions, 5,000 completed candidates, 250 ms traversal deadline (not total HTTP latency). Cancellation and caps return partial status. Display limits are separate from traversal completeness. No beam pruning or unrestricted all-pairs enumeration is used.

## Feature mapping

Commercial fit and cross-account experience: B=1 traced adjacent fit; B=2 one distinct accepted order scoped to the component/facility; B=3 at least two distinct accepted orders. Two orders is an explicit POC repeated-work threshold, not a validated industry threshold. Order copies and split revenue recognition do not count as additional orders. Shared underlying accepted-order lineage remains shared across supplier and facility projections.

Contact candidates: a published role gives B=1 only in this mode, never access. Documented access requires a valid explicit introduction; B=3 applies to that scoped introduction only. Current input role targets and real public candidates have no person-to-person introduction assertions. Do not attach simulated role interactions to public people.

R=3 for an explicitly scoped component objective when every substantive edge matches the declared source/target component; otherwise supported family-level paths receive R=2. Mere sector adjacency is excluded by actionable predicate templates. E is the weakest material assertion: direct scenario/public fact 3, scoped public source with limitations 2, traced inference/assumption 1, absent/conflicting 0. Direct scenario evidence remains scenario evidence.

F uses relation-specific POC tolerances: public role observations 90 days; accepted historical experience the requested lookback (default 365 days), with dated accepted work in the latest 90 days receiving 2; other dated contextual claims 365 days receive 1. Explicit validity covering the query receives 2. Unknown/outdated dates receive 0. Access additionally requires a known observation and unexpired validity. These tolerances are provisional, not industry standards. No capability edge promises current capacity.

Coverage currently freezes four applicable material-assertion fields: resolved identity, scoped component/role, supporting evidence and observation date. Missing dates remain in the denominator. Broader objective-specific capacity/qualification fields are separate execution decisions, not silently inferred observations.

Utility: clamp `100*(.40*B/3 + .25*R/3 + .20*E/3 + .10*F/2 + .05*C) - 2*(hops-1)` to 0..100. Recommend only eligible B>=2, R>=2, E>=1 paths. Constraints group blocked versus needs-check separately; no currently imported edge establishes feasible new capacity.

## Alternatives and sensitivity

First route is highest raw utility, canonical path-ID tie-break. Up to two alternatives, within 15 raw points and the same mode/status, maximize `utility/100 - .20*max_redundancy`. Redundancy is .50 edge-lineage Jaccard + .30 non-endpoint-node Jaccard + .20 source-lineage Jaccard; empty overlap is zero. Exact copies are omitted. This greedy selection is not a globally optimal diverse set. Five explicit coefficient configurations transfer five percentage points between factors; API sensitivity reports whether the first recommendation changes. Business validation remains outstanding.

## Qualification boundaries

`test_canonical_route_search.py` compares the actual search against an independent small exhaustive permutation oracle and tests direction, scope, expiry, cycles, parallel edges, truncation and depth. `test_relationship_imported_scene.py` imports a financially reconciled isolated D2 fixture through normal persistence/projection/service; longer scoped accepted work outranks a shorter inferred fit without removing eligible direct accepted-work routes. Real eleven-account scene evidence is maintained outside the repository. Browser, Omni and hosted qualification are separate gates and cannot be inferred from these tests.
