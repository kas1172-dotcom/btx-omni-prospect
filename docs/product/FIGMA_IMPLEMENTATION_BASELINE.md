# Figma implementation baseline

## Purpose and source

This is the Phase 8A visual-convergence baseline for Phase 9. It was created
from direct Figma design-context inspection of the current file
`QPWPGGDAxEtzG6a69Nsr68`, Page 1. The inspected current nodes are:

- `Command Center - desktop` (`4:7`), including shell, sidebar, top bar, and
  collapsed Omni trigger;
- `Intelligence Monitor — desktop` (`4:205`);
- `Account Portfolio — desktop` (`4:370`);
- `Account Workspace — full detail concept` (`21:245`);
- `Tactical Map — desktop` (`13:2`);
- `Actions - desktop` (`11:5`); and
- `ai-assistant-drawer` (`11:326`).

The shared treatments were also directly inspected in context: the global
search control (`4:42`), a KPI/card panel (`4:50`), READY status chip (`4:45`),
selected navigation control (`4:17`), and Map Layers filter (`30:6`). The
current Figma establishes the intended dark workspace, left navigation, top
bar, compact KPI cards, evidence-oriented panels, status chips, and floating
Omni trigger.

Figma is authoritative for the approved visual direction described here. The
running application remains authoritative for behavior, canonical IDs, current
data, routing, score calculation, evidence state, and workflow semantics.
Figma example copy, counts, account scores, owners, due dates, and its older
scenario-coverage examples are **not** runtime facts and must never be copied
into application logic or static UI content.

## Shared-system decisions

| Area | Baseline decision | Phase 9 implementation note |
|---|---|---|
| Information hierarchy | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt the desktop workspace hierarchy: persistent navigation, page title/context, concise summary cards, then evidence/work panels. Retain all accepted route/state behavior. |
| Navigation | ADOPT WITH FUNCTIONAL PRESERVATION | The Figma sidebar treatment is the target visual shell. Preserve Today, Accounts, Intelligence, Map, Actions, and **Monitor** navigation; do not remove Monitor because the inspected Figma core navigation predates it. |
| Color palette | ADOPT | Use the Figma dark navy surfaces, cyan primary accent, and distinct success/warning/danger treatments through the existing token layer. Keep accessible contrast and semantic state colors. |
| Typography | ADOPT | Use the Figma Inter-based hierarchy, compact uppercase eyebrow labels, and clear page/title/body scale through existing frontend typography. |
| Spacing and density | ADOPT | Adopt the compact, desktop-first spacing rhythm and grouped panels; do not conceal provenance, SAMPLE notices, filters, or action controls to achieve density. |
| Cards and panels | ADOPT WITH FUNCTIONAL PRESERVATION | Figma's bordered dark cards and panel headers map to `Panel`, `State`, and existing surface layouts. Preserve empty, loading, missingness, and evidence states. |
| Tables and lists | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt list/table visual treatment while preserving canonical ordering, IDs, selection, keyboard access, and bounded visible-record context. |
| Filters and search | ADOPT WITH FUNCTIONAL PRESERVATION | Apply the visual control language only. Existing filter values, active-filter transport, clearing, and Omni `context_used` behavior remain canonical. |
| Status and severity | ADOPT WITH FUNCTIONAL PRESERVATION | Figma chips inform presentation only. Existing evidence, validation, work-item, and alert states control the label/color; no state may be upgraded visually. |
| Account 360 | ADOPT WITH FUNCTIONAL PRESERVATION | Use the richer account-detail workspace composition, but retain canonical score, factor coverage, public facilities, public contacts, SAMPLE commercial context, and source links. |
| Map presentation | ADOPT WITH FUNCTIONAL PRESERVATION | Apply Figma's surrounding controls/panel polish while retaining the live MapLibre canvas, verified coordinates, layer/filter behavior, and non-inferential geography rule. |
| Actions presentation | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt the workbench/list/detail visual organization while retaining session-only workflow truth, canonical status/priority/evidence, and explicit confirmation boundaries. |
| Omni collapsed/expanded | ADOPT WITH FUNCTIONAL PRESERVATION | Use Figma's floating assistant trigger and drawer visual language. Preserve free-form read-only use, typed request context, `context_used`, bounded `conversation_referent`, and browser-held continuity. |

## Screen-by-screen convergence matrix

| Surface | Current Figma frame/component reference | Application route/component | Decision | Important discrepancy and Phase 9 note |
|---|---|---|---|---|
| Application shell | `Command Center - desktop` (`4:7`), `sidebar-navigation` (`4:8`), `top-bar` (`4:37`) | `apps/web/src/app/App.tsx`, `design/tokens.css`, `design/app.css` | ADOPT WITH FUNCTIONAL PRESERVATION | Figma uses a left rail; the app uses a top navigation bar. Converge to the rail without losing surface changes, passive context clearing, or accessibility. |
| Today | `Command Center - desktop` (`4:7`) | `features/today/Today.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt KPI/priority/evidence panel layout. Replace all static Figma counts, movers, and urgency copy with canonical Today ordering and current SAMPLE/public disclosures. |
| Accounts | `Account Directory - desktop` / `accounts-portfolio` in `01 - CORE PRODUCT SCREENS` | `features/accounts/Accounts.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Keep curated/all-researched scope, industry filters, exact account selection, and visible-record IDs. Figma's example ranks and accounts are presentation examples only. |
| Account Detail / Account 360 | `concept-account-detail-workspace` in `03 - CONCEPT` | `features/accounts/Accounts.tsx` (`AccountDetail`) | ADOPT WITH FUNCTIONAL PRESERVATION | The concept is visually richer than the current detail stack. Adopt layout incrementally without collapsing public evidence, score gaps, verified facilities, or explicit SAMPLE commercial boundaries. |
| Intelligence | `Intelligence Feed - desktop` / `intelligence` in `01 - CORE PRODUCT SCREENS` | `features/intelligence/Intelligence.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Preserve event selection, source URLs, evidence/validation state, unresolved associations, and typed selected-event Omni context. Do not turn an example signal into a runtime fact. |
| Map | `Tactical Map - desktop` / `tactical-map` in `01 - CORE PRODUCT SCREENS` | `features/map/Map.tsx`, `features/map/MapCanvas.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Figma can guide controls, cards, and map framing. MapLibre, verified facilities, supported markers, selected facility/account state, and no inferred event geography remain mandatory. |
| Actions | `Actions - desktop` / `actions` in `01 - CORE PRODUCT SCREENS` | `features/actions/Actions.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Preserve governed queue/detail behavior, active filters, canonical work-item identity, evidence, session-only disclosure, preview/confirmation gating, and no autonomous Omni writes. |
| Monitor | `Intelligence Monitor — desktop` (`4:205`) | `features/monitor/Monitor.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt the shell, source-status, filter, and evidence-list presentation. Do **not** adopt its `RUN NEW MONITOR` control or static examples: accepted runtime Monitor remains fail-closed, curated/live distinctions remain explicit, and no schedule or collection is started from the UI. |
| Omni collapsed | `ai-trigger` (`131:2`) on `Command Center - desktop` | `components/OmniDrawer.tsx` (`omni-launch`) | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt the floating trigger treatment while preserving the always-available, accessible drawer entry point. |
| Omni expanded | `ai-assistant-drawer` (`11:326`) | `components/OmniDrawer.tsx` | ADOPT WITH FUNCTIONAL PRESERVATION | Adopt visual hierarchy only. Preserve read-only boundary, citations/missingness/recommendation fields, typed context, browser-held referent, and no assistant-text entity parsing. |
| Map opportunity concept | `concept-map-opportunity` in `03 - CONCEPT` | No matching accepted surface | DEFER | Do not turn this concept into new opportunity behavior during Phase 9 without a separately approved product scope. |
| Relationship Intelligence visual UI | `concept-relationship-network`, `Account Portfolio Matrix`, and `List Matrix` in `03 - CONCEPT` | Relationship semantics only: backend service and Omni route | DEFER | This is explicitly Phase 9B. Do not build a graph canvas, relationship matrix, or introduction workflow as part of generic Phase 9 convergence. |
| Auth and settings concepts | `Auth` and `settings-nav-row` (`78:2`) | Development POC shell only | DO NOT ADOPT | There is no accepted production authentication/settings scope. Do not imply identity, permissions, or settings behavior from static Figma treatments. |
| Figma scenario coverage / decision diagrams | Current Page 1 supporting frames | Canonical scenario docs, services, and tests | DO NOT ADOPT AS DATA OR LOGIC | The inspected Figma material contains older scenario/example mappings. Use it only as a visual reference; Phase 7's reconciled canonical scenario matrix and source/SAMPLE evidence remain authoritative. |

## Major Figma ↔ application discrepancies

- **Shell:** the Figma baseline is a sidebar desktop workspace, while the current
  application uses a top navigation bar. Phase 9 may converge the shell visually
  but must retain every accepted surface and context-clearing behavior.
- **Monitor:** Figma has `Intelligence Monitor — desktop` (`4:205`), but its
  run-control treatment cannot become runtime behavior. The app's fail-closed
  Monitor status, curated preview distinction, and no-scheduler boundary win.
- **Static examples:** the Figma command-center frame contains placeholder-like
  KPI values, scores, account examples, owners, due dates, and action text. The
  app must render current canonical records, never these values as facts.
- **Scenario material:** the Figma scenario-coverage content predates Phase 7
  reconciliation. The canonical definitions in `RICH_PUBLIC_SCENARIO_MATRIX.md`
  and `SELLER_POC_OPERATION.md` win.
- **Account detail:** Figma's Account 360 workspace is conceptually richer than
  the current component. Visual composition is adoptable; it must not hide
  missing score coverage, source limitations, or the public/SAMPLE separation.
- **Relationship graph:** Figma visualizes a relationship network, but its
  visual UI is deferred. Existing relationship evidence can remain available
  through Omni until Phase 9B.
- **Controls:** Figma Map examples include static `Current customers` and
  `Top 100` filters, and Actions includes static quick CRM/export controls.
  Phase 9 may adopt control styling only; unsupported filters, exports, and
  actions cannot be implied or added through visual convergence.

## Functional-preservation requirements for Phase 9

The following are non-negotiable during visual convergence:

- Canonical entity IDs and selection across Accounts, Intelligence, Map, and
  Actions; passive selection clearing remains distinct from conversational
  continuity.
- Seller-scenario workflows and canonical Account Attractiveness/ranking
  semantics; no Figma score, priority, or scenario example becomes a competing
  decision rule.
- Public Intelligence source links, evidence/validation states, unresolved
  associations, and the prohibition on inferred event geography.
- Verified facility/map behavior, MapLibre rendering, filter state, and the
  prohibition on treating proximity as a relationship or score input.
- Governed Actions state, canonical `WorkItem.id`, confirmation gates,
  session-only persistence truth, and no autonomous write path.
- Explicit public versus current SAMPLE commercial/CRM/quote/workflow/scoring
  labeling, including missing and conflicting evidence.
- Omni's free-form use, typed surface/selection/filter/visible-ID context,
  truthful `context_used`, bounded typed conversational referent, citations,
  and read-only boundary.
- Account Workspace's Figma Relationship tab is visual structure only until
  Phase 9B; it cannot expose a graph, introduction, or unsupported relationship
  action during ordinary Account 360 convergence.

## Deferred boundaries

- **Phase 9B:** Relationship Intelligence visual UI, including the Figma graph,
  portfolio matrix, and list-matrix concepts.
- New scoring, Monitor relevance, monitoring schedule, workflow, relationship,
  or Omni capabilities are out of scope for visual convergence.
- Authentication/settings product behavior, mobile-product redesign, deployment,
  and architecture rewrites require their own approved scope.
