# Map Screen State Audit — 2026-09-20

## 1. Verdict

The Tactical Map is intended to help a seller explore the national geography of canonical organizations, verified public/reference sites, BTX facilities, and eligible public-intelligence events, then carry a selected account or facility into Organization 360, relationship exploration, Omni, a shortlist, or an itinerary; proximity is explicitly planning context, not evidence of fit ([`apps/web/src/features/map/Map.tsx:109-120`](../../apps/web/src/features/map/Map.tsx), [`docs/product/POC_CAPABILITY_MANIFEST.md:27`](../product/POC_CAPABILITY_MANIFEST.md), [`docs/product/PHASE_18_RELATIONSHIPS_MAP.md:11-17`](../product/PHASE_18_RELATIONSHIPS_MAP.md)). **Verdict: partially functions today.** The canonical API and non-provider UI model are functioning in this checkout: `GET /api/map` returned HTTP 200 with 431 mapped account-site records, 431 facility records, five BTX facilities, and 17 location-pending accounts, and all scoped unit tests passed. The actual basemap cannot function in a normal local build because `VITE_GOOGLE_MAPS_API_KEY` is referenced but neither set in the process nor populated in tracked configuration; the UI therefore intentionally displays “Interactive map unavailable in this build” while preserving the synchronized list ([`apps/web/src/features/map/MapCanvas.tsx:28-35,103-108`](../../apps/web/src/features/map/MapCanvas.tsx), [`apps/web/.env.example:6-10`](../../apps/web/.env.example)). The September 2026 tester's exact symptom cannot be reconstructed, so a missing/invalid key is a confirmed condition of this checkout but only a suspected explanation of that historical report.

All figures in this report describe committed sample/simulated or sanitized-reference data, not real BTX operational performance ([`apps/web/src/app/App.tsx:509`](../../apps/web/src/app/App.tsx)).

## 2. File inventory

| Area | Files and ownership in the Map path |
|---|---|
| Route/shell | `apps/web/src/app/destinations.ts` (Map destination, line 27); `apps/web/src/app/App.tsx` (lazy surface, state, load, render, selection context, lines 19, 43-77, 279-282, 331, 372-390, 459-476) |
| Main UI | `apps/web/src/features/map/Map.tsx`; `MapCanvas.tsx`; `MapFilterPanel.tsx`; `MapAccountDetails.tsx`; `ItineraryPlanner.tsx`; `mapModel.ts`; `mapPresentation.ts`; `map.css` |
| UI contracts/client | `apps/web/src/types/api.ts:36-60`; `apps/web/src/api/client.ts:52-56` |
| Frontend configuration | `apps/web/.env.example:6-10`; `apps/web/README.md:3-7`; `apps/web/package.json:16,23`; `apps/web/tsconfig.app.json:7`; `apps/web/playwright.config.mjs:14-56` |
| Backend endpoint | `backend/src/btx_omni/api/map.py` (router and complete projection); `backend/src/btx_omni/app.py` (router registration); `backend/src/btx_omni/api/accounts.py:83` and `backend/src/btx_omni/api/runtime.py:52-98,235-257` (runtime dependency/composition) |
| Commercial/detail helpers | `backend/src/btx_omni/modules/commercial/map_context.py`; `backend/src/btx_omni/modules/commercial/briefing.py`; `backend/src/btx_omni/modules/scoring/account_attractiveness.py`; `backend/src/btx_omni/modules/federal_procurement.py`; `backend/src/btx_omni/monitor/briefs.py` (imports are explicit at `backend/src/btx_omni/api/map.py:13-28`) |
| Domain/models | `backend/src/btx_omni/domain/accounts.py:130-160`; `backend/src/btx_omni/domain/btx.py:11-23`; `backend/src/btx_omni/providers/sample/environment.py:65-100`; `backend/src/btx_omni/persistence/models.py:19-36,547-628` |
| Fixture loaders | `backend/src/btx_omni/providers/research/ingestion.py:191-217`; `backend/src/btx_omni/providers/research/reference_data.py:31-131`; `backend/src/btx_omni/providers/research/btx_profile.py:21-48`; `backend/src/btx_omni/providers/sample/environment.py:109-148`; `backend/tools/import_sanitized_reference_data.py:243-257` |
| Fixture data | `docs/research/btx_public_facility_feed_enrichment.json`; `docs/research/btx_sanitized_reference_data.json`; `docs/research/btx_company_profile.json:202`; Monitor/sample event inputs loaded through `backend/src/btx_omni/providers/sample/environment.py:85-95` |
| Schema/migrations (inventory only; not changed) | `backend/alembic/versions/0008_commercial_and_edges.py:24`; `backend/alembic/versions/0009_btx_facility_location_metadata.py:35-43`; account-facility columns at `backend/src/btx_omni/persistence/models.py:19-36`; BTX facility columns at `backend/src/btx_omni/persistence/models.py:614-628` |
| Tests | `apps/web/tests/map-model.test.mjs`; Map assertions in `apps/web/tests/poc-ui.test.mjs:211-233`; `apps/web/e2e/map-v2.spec.mjs`; `apps/web/e2e/map-details.spec.mjs`; `backend/tests/test_map_workspace.py`; `backend/tests/test_map_commercial_context.py`; acceptance assertions in `backend/tests/test_api_acceptance.py:70-90`; fixture tests in `backend/tests/test_public_facility_enrichment.py` and `backend/tests/test_sample_provider_foundation.py:30-53` |

There is no dedicated Map hook or independent Map state store. State is React-local in `Map.tsx:22-31`, with navigation snapshots owned by `App.tsx:43-77,279-282`. There is no Map-specific seed script: runtime data is assembled directly from committed fixtures by `build_sample_environment()` (`backend/src/btx_omni/providers/sample/environment.py:109-148`).

## 3. Documented purpose

### Documented intent

| Requirement | Source/section |
|---|---|
| Phase ownership is **Phase 18 — Relationship Intelligence and Tactical Map**. | `docs/product/PHASE_18_RELATIONSHIPS_MAP.md:1,11` (“Tactical Map”). |
| User/job: a seller explores organizations, facilities and nearby opportunities; the destination contract says “Explore organizations, facilities, and nearby opportunities.” | `apps/web/src/app/destinations.ts:27`; the product calls it a “seller workspace” in `backend/src/btx_omni/api/map.py:1`. |
| National graph must render only loaded researched locations, with researched accounts, public facilities and BTX facilities; supported markets are Defense, Commercial Aerospace, Space, Robotics, Semiconductor, Medical and Energy. Proximity is planning-only. | `docs/product/POC_CAPABILITY_MANIFEST.md:27` (“National commercial graph”). |
| Account/intelligence pins require canonical account/facility identity, verified coordinates and stable IDs. Intelligence also requires a resolved, seller-eligible non-curated brief with current observed or governed upcoming timing. Never use guessed, model-derived, publication, or free-text geography. | `docs/product/PHASE_18_RELATIONSHIPS_MAP.md:13`; `docs/product/SURFACE_CONTRACTS.md:13-14`. |
| Popups keep the map primary and expose facility/intelligence context plus Organization 360 and relationship navigation; mobile uses a compact bottom sheet. | `docs/product/PHASE_18_RELATIONSHIPS_MAP.md:17`; Figma reconciliation says compact controls and selected detail around a governed canvas at `docs/product/PHASE_21_FIGMA_RECONCILIATION.md:14`. |
| Required behaviors included tiles, points, zoom/pan, clusters/expansion, account selection, facility/market filters, selected state, navigation and dynamic updates without full reinitialization. | `docs/planning/POC_EXECUTION_PROMPTS_2026-08-19.md:490-525` (“Phase 4 — Map Completion”). |
| Only verified public HQ/facility coordinates render; unverified locations have no pin. | `docs/product/POC_SAMPLE_ACCEPTANCE_MATRIX.md:12`; `docs/product/PUBLIC_FACILITY_FEED_ENRICHMENT.md:18`. |
| Account-point selection supplies account context; facility selection supplies its facility ID and parent account only when present; BTX facility supplies only facility ID. | `docs/product/SURFACE_CONTRACTS.md:29-32`. |
| Map was a Phase 1 top-level surface and was claimed visually matched with zero blocking differences in the earlier reconciliation. | `docs/product/POC_CAPABILITY_MANIFEST.md:9`; `docs/product/PHASE_21_FIGMA_RECONCILIATION.md:21-25`. |

### Inference (not a stated requirement)

The decision question appears to be: **“Which verified organizations/sites/events are geographically relevant to my seller planning, and what governed account context should I inspect next?”** This is inferred from the page copy and destination job (`Map.tsx:110`, `destinations.ts:27`), not quoted as a formal product question. Likewise, itinerary and shortlist mutation are current implemented extensions (`Map.tsx:98-105,120,126`; `client.ts:53-56`), but the Phase 18 purpose statement does not explicitly require them.

The documentation is internally stale about provider choice. `docs/product/SELLER_POC_OPERATION.md:9-22`, `docs/architecture/CODE_REVIEW_REFERENCE.md:127,285-286`, and the 2026-08-19 plan at lines 735 and 850 say MapLibre/MapTiler; current code and current web README explicitly use Google Maps (`MapCanvas.tsx:28-53`; `apps/web/README.md:3-7`).

## 4. Current behavior summary

### Provider and configuration

The live renderer uses `@googlemaps/js-api-loader`, imports Google `maps` and `marker` libraries, and creates `google.maps.Map` plus `AdvancedMarkerElement` markers (`apps/web/package.json:16,23`; `MapCanvas.tsx:1,38-53,61-83`). It needs `VITE_GOOGLE_MAPS_API_KEY`; `VITE_GOOGLE_MAPS_MAP_ID` is optional and defaults to `DEMO_MAP_ID` (`MapCanvas.tsx:28`). The key is declared blank in tracked `.env.example` and was absent from the audit process environment (`apps/web/.env.example:6-10`): **CONFIRMED unconfigured in this checkout**, though deployment secrets were not inspected.

### Plotted entities and coordinates

| Entity | Coordinate field consumed by UI | Current inclusion rule |
|---|---|---|
| Account/customer/prospect site | `record.coordinates.latitude/longitude` (`mapModel.ts:29-33`) | One account record per eligible canonical facility; only `PROSPECT` is styled as prospect, all other segments as customer (`mapModel.ts:16,33`). |
| Public/reference facility | `facility.coordinates.latitude/longitude` (`mapModel.ts:34-39`) | Visible only when the public-facilities layer is enabled and its parent account survived account filters (`Map.tsx:53-58`). |
| BTX facility | `facility.coordinates.latitude/longitude` (`mapModel.ts:40-45`) | Visible when BTX layer enabled; independent of account filters. |
| Intelligence/current or upcoming event | `signal.coordinates.latitude/longitude` (`mapModel.ts:46`) | Coordinates are copied from the brief's exact canonical facility, not the event text (`api/map.py:105-129,396-425`). No programs or opportunities are plotted as independent markers. Federal opportunities are nested account detail only (`api/map.py:348-350`). |

Default layers are customers, prospects and BTX facilities; public facilities and intelligence default off (`mapModel.ts:10-11`). Filters cover text, rich/all coverage, Top 100, market, relationship segment, layers, current/upcoming timing, strategic-partnership inclusion, saved shortlist, 30/50/100-mile radius, NAICS, business unit, capability and fulfillment state (`mapModel.ts:7,17-27`; `MapFilterPanel.tsx:20-86`). Radius is straight-line Haversine from the selected marker (`mapModel.ts:49-56`).

Account/prospect markers cluster within a 48-pixel world-space radius; selected and non-account markers stay outside those clusters. Intelligence appears at zoom 5+, public facilities at zoom 7+, while accounts/prospects/BTX facilities remain eligible at all zooms (`mapModel.ts:57-92`). Encodings are categorical shape/fill, not value size: customer filled circle, prospect outlined circle, public facility diamond, BTX square, intelligence pin/upcoming dashed marker, and numbered cluster (`map.css:1,4-8`). There is no score-driven marker size/color.

Clicking a marker selects it; clicking a cluster fits bounds or exposes coincident members; selected records pan/zoom or frame the account site and nearest BTX site (`MapCanvas.tsx:65-102`). There is no authored hover behavior beyond provider titles. The detail panel offers account/facility/intelligence evidence, Organization 360, relationships, Omni, shortlist, and itinerary actions (`Map.tsx:74-105,120-126`).

Loading/error/empty behavior is explicit. The shell shows a loading status and a retryable resource error, retaining last-good content if available (`App.tsx:511-514`). No key shows “Interactive map unavailable in this build” but leaves the synchronized list/details; provider or marker-load failure shows “Map unavailable” with configuration guidance (`MapCanvas.tsx:53,83,103-108`). No matching marker shows “No verified markers match…” plus Clear filters (`Map.tsx:118`). Location-less matching accounts remain in a “Location pending” list rather than receiving fabricated coordinates (`Map.tsx:113`; `api/map.py:244-264`). Tile failure after successful Google initialization is not separately observed by app code; provider behavior controls it.

## 5. Data lineage and coordinate coverage

`GET /api/map` is not a SQL-backed Map query in SAMPLE mode. It calls `runtime.environment()`, which composes committed research/reference fixtures (`api/map.py:155-160`; `environment.py:109-148`). Therefore “source table” counts below are runtime collections/fixture rows. Database tables exist (`persistence/models.py:19-36,547-628`) but no local PostgreSQL was available, and the endpoint did not query them; DB row counts are **not run**, not zero.

| Plotted entity | UI → API → endpoint/query → source | Runtime source rows / usable coordinates | Cannot appear / notes |
|---|---|---:|---|
| Account site | marker `record.coordinates` (`mapModel.ts:33`) → `accounts[].coordinates` (`types/api.ts:38`) → `/api/map` loops each selected account and matching facility (`api/map.py:177-182,231-320`) → `SampleEnvironment.accounts` joined in memory to `facilities` by `facility.account_id` (`api/map.py:234-243`) | 309 canonical accounts; 292 accounts have at least one eligible facility and produce 431 site rows; all 431 output coordinates usable. 17 accounts are pending. | The 17 with no eligible join cannot produce account pins; they are explicitly returned pending (`api/map.py:244-264`). Accounts have no coordinate columns in the domain; coordinates are facility-scoped by design (`PHASE_18_RELATIONSHIPS_MAP.md:13`). |
| Public/research facility | marker `facility.coordinates` (`mapModel.ts:34-38`) → `facilities[].coordinates` (`types/api.ts:39`) → `facility_points` (`api/map.py:357-376`) → union of public-feed and sanitized-reference fixtures (`environment.py:110-135`) | 39 public-feed + 392 sanitized-reference = 431 facilities; 431/431 usable. | Public-feed rows are accepted only for verified HQ/facility records with latitude (`ingestion.py:191-217`). Reference loader validates both coordinate ranges (`reference_data.py:113-127`). No geocoding occurs at request time. |
| BTX facility | marker `facility.coordinates` (`mapModel.ts:40-44`) → `btx_facilities[].coordinates` (`types/api.ts:40`) → `btx_points` (`api/map.py:377-395`) → `docs/research/btx_company_profile.json` loader (`btx_profile.py:21-48`) | 5 source/runtime rows; 5/5 usable and returned. | Loader permits missing coordinate pairs but endpoint filters them (`btx_profile.py:33-39`; `api/map.py:172-176`). None are excluded today. |
| Intelligence | marker `signal.coordinates` (`mapModel.ts:46`) → `intelligence[].coordinates` (`types/api.ts:46`) → governed brief projection (`api/map.py:66-129,401-425`) → Monitor brief plus exact canonical facility join | Current response: 0 returned / 0 usable. | A brief is excluded unless resolved, seller-eligible, non-curated, correctly timed, and joined to a canonical facility belonging to the selected account (`api/map.py:84-102,403-417`). Thus current sample events do not produce Map event markers. |

Coordinate origin is stored fixture latitude/longitude. The public enrichment's own metadata requires authoritative verification and allows approximate city-center coordinates where documented (`docs/research/btx_public_facility_feed_enrichment.json:6-7`); runtime construction converts those stored numbers to `Decimal` (`ingestion.py:211-216`). Sanitized-reference and BTX points are also stored, range-validated fixture fields (`reference_data.py:113-127`; `btx_profile.py:33-46`). There is no runtime geocoder and no frontend hardcoded entity location. The only frontend hardcoded geography is the neutral initial U.S. camera center `{lat: 38, lng: -98}` (`MapCanvas.tsx:43`), which is not a data marker. The test renderer deliberately lays markers into a deterministic grid and is enabled only by `VITE_MAP_TEST_MODE=true` (`MapCanvas.tsx:28-35,104`; `playwright.config.mjs:40-48`).

## 6. Verification results and defects

### Commands and outcomes

| Command | Result | Baseline comparison |
|---|---|---|
| `npm run typecheck` | PASS | No baseline supplied. |
| `npm run lint` | PASS | No baseline supplied. |
| `npm run build` | PASS; Vite built 101 modules. | No baseline supplied. |
| `npm test` (the requested map-pattern argument was not consumed by this script, so the full frontend unit suite ran) | PASS: 83/83. Map-model cases cover coordinate validation, filtering, clustering and zoom thresholds (`apps/web/tests/map-model.test.mjs:8-79`). | No baseline supplied. |
| `UV_PROJECT_ENVIRONMENT=/tmp/btx-venv UV_LINK_MODE=copy uv run pytest tests/test_map_workspace.py tests/test_map_commercial_context.py -q` | PASS: 12/12, one deprecation warning. | No baseline supplied. |
| In-process TestClient `GET /api/map` | PASS: HTTP 200; payload counts stated in section 5; contract keys match `client.ts:52` and `types/api.ts:36-60`. | No baseline supplied. |
| `uv run pytest -q` | MIXED: 708 passed, 69 failed, 10 errors. PostgreSQL-parametrized errors lack `BTX_DATABASE_URL`; other failures include release input/hash drift, migration-head drift, and unrelated Omni/scoring assertions. Map-specific suite passed. Per task instruction, PostgreSQL cases are **not run**, not Map defects. | No baseline supplied. |
| `npx playwright test e2e/map-v2.spec.mjs e2e/map-details.spec.mjs` | NOT RUN: first attempt found port 8000 occupied; isolated ports then failed before browser launch because `BTX_COMMERCIAL_DURABLE_STATE_ENABLED=true` requires a qualified import (`playwright.config.mjs:14-48`). | No baseline supplied. |

The real Google renderer was **not rendered or qualified**. Test-mode browser coverage exists and expressly substitutes a deterministic renderer (`apps/web/README.md:7`; `map-v2.spec.mjs:14-59`), but this audit could not launch it for the environmental reason above.

### Confirmed findings

1. **CONFIRMED — normal checkout has no configured Google browser key (blocks the interactive basemap locally).** `MapCanvas` refuses provider initialization when the key is absent and renders the explicit unavailable panel (`MapCanvas.tsx:28-35,103-106`); tracked configuration declares an empty value (`.env.example:6-10`). The synchronized list remains usable.
2. **CONFIRMED — API/data/schema path is healthy in the in-process sample runtime.** HTTP 200 and 431/17/431/5/0 entity counts were reproduced; backend map tests passed. Endpoint construction and response keys are at `api/map.py:155-176,231-495` and match `client.ts:52`.
3. **CONFIRMED — intelligence layer is empty with today's sample projection.** The real endpoint returned zero intelligence points. This does not crash the map; it leaves that optional layer empty under the admission rules (`api/map.py:84-102,401-425`). It degrades the promised intelligence geography.
4. **CONFIRMED — 17 accounts cannot be mapped because no eligible facility join exists.** They are not silently dropped: the endpoint emits `pending_accounts` without coordinates (`api/map.py:244-264`) and the UI lists them (`Map.tsx:113`).
5. **CONFIRMED — API failure does not render Map content until a successful resource exists.** The shell shows a retryable error and only renders once `resourceReady.map` is true (`App.tsx:331,513-514`). This is handled, not an unhandled exception.
6. **CONFIRMED — CSS gives the map a non-zero constrained height.** `.map-stage` and `.map-canvas` use explicit/flex heights, including mobile minimums (`map.css:1,22-45`); zero-height is not supported by code inspection or build results.
7. **CONFIRMED — browser-only globals are confined to effects/render-time paths in a Vite client app.** `window`, `ResizeObserver`, and `google.maps` are used in `MapCanvas.tsx:29,34-56,86-108`; this build has no SSR path, and production build/typecheck passed. SSR is not a current failure.
8. **CONFIRMED — documentation/provider drift.** Product/architecture docs say MapLibre/MapTiler (`SELLER_POC_OPERATION.md:9-22`; `CODE_REVIEW_REFERENCE.md:127,285-286`), while code uses Google (`MapCanvas.tsx:28-53`).

### Suspected/unverified failure points

1. **SUSPECTED historical cause — missing, invalid, referrer-restricted, billing-disabled, or quota-exhausted Google key.** All are translated to provider-load failure copy (`MapCanvas.tsx:38-53`), but the prior tester's observation and deployment configuration are unavailable.
2. **SUSPECTED — post-initialization tile/auth failure may show Google's provider error rather than the app's `Map unavailable` state.** The code catches library initialization and marker import, but has no Google tile/auth event listener (`MapCanvas.tsx:38-83`). This was not rendered with a real key.
3. **SUSPECTED — the default `DEMO_MAP_ID` may be unsuitable for a production-key deployment or advanced-marker policy.** It is the fallback (`MapCanvas.tsx:28,43`), but cannot be tested without the deployment's Google configuration.
4. **Not supported by evidence:** empty account payload, null-coordinate crash, API/UI response-shape mismatch, zero-height container, or SSR failure. Current payload, types, CSS, tests and build contradict those candidate causes (`types/api.ts:36-60`; `mapModel.ts:14-47`; `map.css:1,22-45`).

## 7. Cross-screen inconsistencies

No account value conflict was reproduced between Map and the Accounts/Organization 360 source projection. A programmatic comparison of all 431 Map site rows against `GET /api/accounts` found zero differences for canonical `relationship` and Account Attractiveness value; Boeing, for example, is `CURRENT_CUSTOMER` and `95.00` in both. This consistency is expected because Map derives relationship from the canonical account and calls the same attractiveness projection (`api/map.py:299-332`), while Map and Account 360 deliberately share the same commercial briefing owner (`api/map.py:427-467`).

Location presentation differs in cardinality but is not a contradiction: Accounts exposes one representative `location`, while Map emits every eligible facility per account (`api/map.py:234-243,278-356`); the selected Map facility is preserved when opening Organization 360 (`App.tsx:170-171,468-472`). Today was not found to duplicate Map coordinates; Map context is carried by canonical account/event IDs (`App.tsx:459-476`). A complete rendered Today-to-Map visual comparison was not possible because Playwright could not start.

One semantic inconsistency remains: `relationshipKind()` treats every segment other than `PROSPECT`—including `DORMANT_CUSTOMER` and `UNKNOWN`—as a `customer` marker (`mapModel.ts:16`), while the filter UI separately labels dormant and unknown states (`mapPresentation.ts:4-8`). Values are unchanged, but the marker legend can visually overstate “customer.”

## 8. Ranked gap list

| Rank | Severity | Gap | Evidence |
|---:|---|---|---|
| 1 | **Blocks demo** | A normal build without `VITE_GOOGLE_MAPS_API_KEY` cannot display the interactive basemap. This checkout has no set key. | `MapCanvas.tsx:28-35,103-106`; `.env.example:6-10`. |
| 2 | **Blocks demo qualification** | Real Google tiles, auth/referrer restrictions, billing/quota, advanced markers, pan/zoom and live error behavior are unqualified; deterministic test mode cannot qualify them. | `backend/docs/browser-qualification.md:11`; `apps/web/README.md:7`; failed Playwright startup noted above. |
| 3 | **Degrades demo** | Intended public-intelligence geography is empty today: endpoint returns zero eligible markers. | Required by `PHASE_18_RELATIONSHIPS_MAP.md:13`; admission/projection at `api/map.py:84-129,401-425`. |
| 4 | **Degrades demo** | 17 of 309 accounts have no eligible facility and therefore no pin, although the pending list truthfully preserves them. | `api/map.py:244-264`; reproduced counts. |
| 5 | **Degrades demo** | Dormant and unknown relationships use the customer marker encoding, despite separate filter labels. | `mapModel.ts:16`; `mapPresentation.ts:4-8`. |
| 6 | **Degrades maintenance/review** | Current Google implementation conflicts with MapLibre/MapTiler requirements and architecture docs, making expected provider behavior ambiguous. | `SELLER_POC_OPERATION.md:9-22`; `CODE_REVIEW_REFERENCE.md:127,285-286`; `MapCanvas.tsx:28-53`. |
| 7 | **Degrades demo** | Provider tile/auth errors after map construction have no application-level listener and may not produce the documented fallback panel. | Only initialization and marker import are caught at `MapCanvas.tsx:38-83`. |
| 8 | **Cosmetic/accessibility semantics** | Legend says Customers although the corresponding marker kind can include dormant and unknown accounts. | `mapModel.ts:16`; `mapPresentation.ts:4-10`. |

## 9. Questions only a human can answer

1. What exactly did the September 2026 tester see: the explicit “Interactive map unavailable” panel, a blank/gray Google canvas, Google authorization text, missing markers, a loading state, or a crash? What URL/build and browser were used?
2. Was `VITE_GOOGLE_MAPS_API_KEY` present when that frontend artifact was built, and were its HTTP-referrer restrictions, Maps JavaScript API enablement, billing and quota valid for the tested hostname?
3. Is Google Maps now the approved provider, superseding the MapLibre/MapTiler requirements, or is the implementation expected to return to MapLibre?
4. Is zero Map intelligence expected for the current sample, or must the demo include at least one governed facility-resolved event?
5. Should dormant and unknown accounts share the “customer” marker/legend, or receive distinct encodings?
6. What is the authoritative baseline for the full backend suite? None was supplied, and this worktree contains unrelated existing changes plus fixture/release-hash drift.

