# Phase 18 — Relationship Intelligence and Tactical Map

## Relationship Intelligence

Relationship Intelligence uses the existing bounded breadth-first traversal over typed, canonical relationship records. It does not implement weighted shortest-path algorithms, Dijkstra, or Yen: those need a future governed weighting model. Paths retain their canonical evidence and are projected by the backend in deterministic order: validated before needs-validation, direct before indirect, fewer hops, source coverage, then canonical IDs.

Seller results are capped at 12 paths. `VALIDATED` paths have sufficient governed evidence; `NEEDS_VALIDATION` paths identify the specific source or inference gap; `UNUSABLE` paths remain diagnostic-only and are excluded from seller planning. The UI shows business-readable connection labels, hop count, why it may matter, advisory suggested moves, dated evidence where supplied, and validation requirements. No strength score, confidence percentage, inferred intent, or introduction probability is presented.

Program ownership alone is context, not a seller-visible path. A program can appear only when another governed relationship basis supports the path.

## Tactical Map

Map account and intelligence markers require a canonical account, a canonical public facility, verified coordinates, and stable canonical IDs. Account locations are facility-scoped; the projection never chooses an HQ as a fallback. Intelligence markers additionally require resolved, seller-eligible, non-curated briefs and either a current observed event or an upcoming event with a governed date. Free text, publication locations, guessed coordinates, and model-derived geography are never mapped.

The provider-neutral marker model owns IDs, coordinates, filters, and popup data; the current renderer remains behind its existing provider seam. Supported layers are Customers, Prospects, public facilities, BTX facilities, and intelligence. Filters combine market, customer segment, BTX Top 100 membership, marker layer, and current/upcoming intelligence timing. Strategic Partnership and Industry Top 100 remain unavailable because no canonical source currently supports them.

Marker popups keep the map primary: they show canonical facility context, applicable intelligence, and Customer 360 / Relationship Intelligence navigation. The mobile selected-item surface is a compact bottom sheet. A Customer without an eligible canonical facility is not mapped.
