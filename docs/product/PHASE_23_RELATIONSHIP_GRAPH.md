# Phase 23 — Relationship Graph Presentation

Phase 23 adds a bounded **Graph view** within Relationship Intelligence. It is a seller-planning presentation of the existing `seller_projection`; it does not create, rank, infer, or validate relationships.

## What the graph shows

- Only seller-eligible `validated` and `needs_validation` paths already returned by the governed projection.
- Stable placement derived from each path's existing step order.
- Existing entity kinds only. The legend and node shape communicate available categories without inventing missing contacts, facilities, programs, or BTX context.
- Solid grayscale connections for validated paths and dashed grayscale connections for paths that require validation.
- A selected node or connection detail panel with the existing path summary, seller rationale, validation requirement, and evidence references.

Unusable paths remain excluded. When no eligible path exists, the graph presents an explicit empty state rather than a blank canvas or fabricated network.

## Boundaries preserved

The list views remain the primary workflow: **Validated connections** and **Connections to review**. The graph is subordinate progressive disclosure and preserves deterministic bounded traversal, direct-before-indirect ordering, fewer-hop preference, source-backed tie-breaking, and `VALIDATED` / `NEEDS_VALIDATION` / `UNUSABLE` semantics supplied by the backend.

It intentionally has no confidence or strength score, warm-introduction claim, probability, graph algorithm, provider lookup, or Gemini authority. The responsive layout stacks the selected context below the graph when space is limited.
