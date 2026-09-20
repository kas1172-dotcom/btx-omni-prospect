# Map Rework Decision Log

## 2026-09-20 — Baseline

- Created branch `codex/map-rework` from the current branch.
- Preserved pre-existing Communications worktree changes; Map commits will stage explicit paths only.
- Baseline: frontend typecheck/lint/build/unit tests pass (90/90). Backend: 746 passed, 67 failed, 10 errors, 2 skipped.
- The 10 PostgreSQL journal errors are environmental because no local `BTX_DATABASE_URL`/PostgreSQL is available. Other existing failures remain comparison IDs in `MAP_REWORK_BASELINE.txt`.
- No dependencies added. No tests removed or modified in this step.

## 2026-09-20 — Step 0 findings

- Classified camera hypotheses in `MAP_REWORK_FINDINGS_2026-09-20.md` before application edits.
- Coordinate profiling uses the assembled SAMPLE runtime and `/api/map`; account coordinates are intentionally facility-scoped.
- Top 100 is an existing provenance-backed membership flag from the sanitized Top 100 workbook, not a rank. Decision: preserve it rather than derive a new trailing-revenue ranking, because replacing its semantics would alter data behavior outside Map.
- No dependencies added. No tests removed or modified in this step.

## 2026-09-20 — Step 1 camera

- Added pure `computeViewport` in `mapViewport.ts`; it has no Google Maps imports and rejects invalid points before planning.
- Explicit camera requests now own selection framing. Marker-data changes do not create requests, and the provider adapter refuses to move while its container has zero width or height.
- Small/coincident groups use center + zoom 12; bounds use max zoom 13; selection padding reserves the desktop detail panel or mobile bottom sheet; radius and provider viewport have precedence.
- Cluster clicks remain an explicit camera intent and now receive the same small-spread and max-zoom behavior.
- Added `map-viewport.test.mjs` for zero/one/duplicate/near cluster/US-wide/invalid/viewport/radius/idempotence cases.
- Assumption: “under ~2 km” is represented by 1.25 miles. No dependency added; no test removed or weakened.

## 2026-09-20 — Step 2 search

- Moved search above the Map as a keyboard-operable combobox over the canonical marker array. Local results prioritize BTX sites, then organizations/sites and their stored city/region address text.
- Arrow Up/Down, Enter and Escape are handled; no-match copy is announced as status.
- Selecting a result uses the same explicit marker-selection intent, opens its detail panel, and requests fixed site camera framing.
- No Places provider is configured in this repository beyond the basemap key, so no external prediction request is made. This avoids making local acceptance depend on a key and does not fabricate provider viewports.
- No dependency added; no test removed or modified.

## 2026-09-20 — Step 3 synchronized table

- Replaced the visible sidebar/card list with a fixed-row, sticky-header table below the map. Its scroll container is capped at 320 px; the legacy list DOM remains hidden temporarily for navigation compatibility and will be removed with the filter cleanup.
- The table and map toolbar derive from the same unclustered marker collection. Generated presentation clusters never create duplicate rows.
- Row selection uses explicit marker selection/camera intent. Marker or search selection scrolls the matching row into view.
- Distance is straight-line and appears only while a selected origin exists. Itinerary controls reuse canonical account/facility markers and do not invent travel time or meeting confirmation.
- Added `map-list-model.test.mjs` to assert shared array/count behavior and cluster exclusion.
- No dependency added; no test removed or weakened.
