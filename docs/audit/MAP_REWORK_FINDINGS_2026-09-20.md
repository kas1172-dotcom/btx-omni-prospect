# Map Rework Read-Only Findings — 2026-09-20

## Camera movement inventory

All Google camera movement is currently in `apps/web/src/features/map/MapCanvas.tsx`.

| Line | Movement | Trigger | Inputs |
|---:|---|---|---|
| 43 | Constructor default camera | Map provider initializes after a key and non-null container are available | Hardcoded US center `{lat: 38, lng: -98}`, zoom 4, minZoom 3 |
| 75 | `map.fitBounds(marker.bounds, 80)` | User clicks a generated account/prospect cluster | Cluster bounds from `markersForZoom`; uniform 80 px padding; no max-zoom cap |
| 97-99 | `map.fitBounds(bounds, padding)` | A new selected marker has a multi-marker `selectionFrame` | Bounds of selected site, its related public sites and nearest BTX site; mobile padding `{top:90,left:40,right:40,bottom:45% container height}`, desktop `{top:70,left:70,right:360,bottom:90}`; no max-zoom cap |
| 101 | `panTo`; conditional `setZoom(8)` | A new selected marker has a one-marker frame | Selected marker coordinates; zoom is raised to 8 only when current zoom is below 8 |
| 51 | State-only zoom listener | User/provider changes zoom | Reads provider zoom for client clustering; does not move camera |

There is no `setCenter`, `defaultBounds`, place viewport, radius-circle fit, or general fit-to-results call elsewhere in the Map code. `lastFramed` at lines 88-101 suppresses repeat framing for the same selected marker until the map is reinitialized.

## Coordinate quality

Counts were calculated from `get_runtime().environment()` and the real in-process `GET /api/map` sample payload. “Swapped” can only be proven structurally when the original pair is invalid but reversing it is valid; none met that rule. No external geocoder/address comparison was performed.

| Entity type | Rows | Null pair | 0/0 | NaN/non-numeric | Out of range | Provably swapped | Valid |
|---|---:|---:|---:|---:|---:|---:|---:|
| Canonical account object | 309 | 309 | 0 | 0 | 0 | 0 | 0 |
| Verified public facility source | 39 | 0 | 0 | 0 | 0 | 0 | 39 |
| Sanitized reference facility source | 392 | 0 | 0 | 0 | 0 | 0 | 392 |
| BTX facility source | 5 | 0 | 0 | 0 | 0 | 0 | 5 |
| API account-site markers | 431 | 0 | 0 | 0 | 0 | 0 | 431 |
| API facility markers | 431 | 0 | 0 | 0 | 0 | 0 | 431 |
| API BTX markers | 5 | 0 | 0 | 0 | 0 | 0 | 5 |
| API intelligence markers | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Accounts intentionally have no direct coordinates: Map locations are facility-scoped (`backend/src/btx_omni/api/map.py:161-176,231-320`). Backend `_coordinates` rejects null and out-of-range pairs (`backend/src/btx_omni/api/map.py:34-43`); frontend `validCoordinates` rejects null, blank, booleans, non-finite and out-of-range values (`apps/web/src/features/map/mapModel.ts:12-15`) before marker construction.

## Hypotheses

1. **CONFIRMED in part:** cluster clicks and multi-marker selection frames call `fitBounds` with no max-zoom cap (`MapCanvas.tsx:75,97-99`). A literal single-marker frame does not call `fitBounds`; it pans and conditionally raises zoom to 8 (`MapCanvas.tsx:101`). Coincident/near-coincident multi-marker frames can therefore zoom excessively.
2. **NOT CONFIRMED:** there is no places provider or place viewport today. The text search only filters records (`mapModel.ts:17-27`), and a result-list click does share the normal site `selectMarker` path (`Map.tsx:113`), but it cannot currently discard a provider viewport because none exists.
3. **NOT CONFIRMED:** invalid coordinates do not enter current bounds. Both API and UI validate coordinates, and the live sample projection contains no invalid output pairs (`api/map.py:34-43,163-176`; `mapModel.ts:14-15,29-47`).
4. **NOT CONFIRMED for data-change/every-render fitting; CONFIRMED that size is not checked.** The selection effect is guarded by selected ID and `lastFramed` (`MapCanvas.tsx:86-102`), so ordinary marker refetch/render does not re-fit the same selection. However, it does not require positive `clientWidth/clientHeight` before moving the camera.
5. **CONFIRMED for clusters; NOT CONFIRMED for selection frames.** Cluster fit uses a uniform 80 px and ignores panels (`MapCanvas.tsx:75`). Selection-frame fit explicitly reserves 360 px at desktop right and 45% height at compact bottom (`MapCanvas.tsx:96-99`).
6. **NOT CONFIRMED:** origin/radius currently filters marker data only (`mapModel.ts:56`; `Map.tsx:63-64`). Changing radius does not move the camera at all, so it neither fits results nor the radius circle.

## Top 100 findings

- A boolean `btx_top_100` flag exists end to end. The Map API copies it from canonical accounts into mapped and location-pending records (`backend/src/btx_omni/api/map.py:247-263,306-320`); frontend contracts and filters consume it (`apps/web/src/types/api.ts:36-38`; `apps/web/src/features/map/mapModel.ts:17-27`).
- Runtime counts: 87 of 309 canonical accounts are flagged; all 87 have mapped sites, producing 169 of 431 account-site rows. This is membership, not an ordinal rank.
- The flag is derived without a hardcoded name list: `backend/tools/import_sanitized_reference_data.py:204-235` identifies rows whose source workbook is `Copy of btx top 100 customers 0726.xlsx`, sets membership from the presence of those source references, and writes provenance. The fixture preserves `btx_top_100_references` (`docs/research/btx_sanitized_reference_data.json:77,109-128`). The importer explicitly says no authoritative complete `industry_top_100` ranking exists (`import_sanitized_reference_data.py:262`).
- A separate `ExternalIndustryRank` test exists (`backend/tests/test_account_attractiveness.py:69-71`) but is not the Map's BTX Top 100 source and is not projected as a Map rank.
- History: commit `06cce59842d2872004154e4c96ef312d88a09875` (`feat(data): ingest sanitized customer reference sources`, 2026-08-27) introduced the source-derived flag. Commit `700e5173089e4e813f51680ca1a82c2b027361af` (`feat: complete UX Wave 4 market and map experience`, 2026-09-18) added/retained the Map filter and membership presentation. `git log -S'btx_top_100'` shows later reshaping but no removal or rename of the canonical field. The current Map already contains a Top 100 filter; Step 5 should preserve and test it, not derive a revenue rank.

