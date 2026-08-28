# BTX Omni Prospect — Reference Doc for Code Review

This doc exists to get a software engineer from zero to "I understand what I'm
looking at and why it's built this way" before reviewing this codebase. It is
not a product pitch. Where something is a limitation, a stub, or an unresolved
question, it says so plainly — that's more useful to a reviewer than a polished
story.

---

## 1. What the product is

BTX Omni Prospect is a **governed commercial intelligence and prospecting
platform**. In plain terms: it watches for public events that could signal a
sales opportunity (contract awards, facility expansions, funding rounds), cross-
references them against what BTX (a manufacturing company) already knows about
its own accounts (revenue, quote history, relationships), applies the existing
deterministic scoring rubric where governed SAMPLE scoring inputs exist, and surfaces that —
with full evidence trails — across a small set of UI surfaces. A conversational
layer ("Omni") sits across all of them so a user can ask questions about
whatever they're looking at instead of hunting through screens.

The product also evaluates **existing** customers for governed SAMPLE commercial
signals (inactivity, bookings decline, stale quotes). Workflow actions remain
separately human-confirmed; Monitor collection never writes CRM/workflow state.

**The five user-facing surfaces** (`docs/product/POC_CAPABILITY_MANIFEST.md`):
Today, Accounts, Intelligence, Map, Actions — plus Omni, which is a persistent
capability across all of them, not a sixth tab.

## 2. What it will do vs. what it does today — read this section first

This is the single most important thing to understand before reading any code,
because it explains almost every architectural choice in this repo.

The system is designed around **two data modes**, defined in
`backend/src/btx_omni/domain/common.py`:

```python
class DataMode(StrEnum):
    SAMPLE = "SAMPLE"
    CONNECTED = "CONNECTED"
```

- **SAMPLE** — the mode this POC runs in today. Account identity, public
  facilities, and public intelligence are **real, researched facts** about real
  public companies (with source URLs). Everything that would come from BTX's
  internal systems — PRISM (revenue/bookings), Paperless Parts (quotes), HubSpot
  (CRM) — is **synthetic**, shaped to look like what those systems would return,
  used to prove the operating model works.
- **CONNECTED** — the production mode. Requires real, authorized adapters to
  BTX's actual systems. **It is not a fallback.** If CONNECTED is requested and
  no live provider is wired, the system fails closed rather than silently
  showing SAMPLE data. See `PocRuntime.environment()` in
  `backend/src/btx_omni/api/runtime.py`:

  ```python
  def environment(self) -> SampleEnvironment:
      if self.settings.data_mode.upper() != "SAMPLE":
          raise HTTPException(503, "CONNECTED mode is unavailable: no live providers are configured.")
      return self.sample
  ```

  `backend/src/btx_omni/providers/connected/` exists as the intended extension
  point and currently contains nothing but an `__init__.py`. That's
  intentional, not an oversight — it's where a real PRISM/Paperless/HubSpot
  adapter would be implemented against the same `AccountProvider` /
  `CommercialContextProvider` / `QuoteProvider` protocols
  (`backend/src/btx_omni/providers/contracts.py`) that the SAMPLE provider
  implements today.

Every governed fact in the system carries a `Provenance` record
(`backend/src/btx_omni/core/provenance.py`) that includes `data_mode` and a
`synthetic` boolean, and the dataclass enforces the invariant at construction
time:

```python
if self.data_mode is DataMode.CONNECTED and self.synthetic:
    raise ValueError("connected facts cannot be synthetic")
```

So the SAMPLE/CONNECTED distinction isn't a comment or a naming convention —
it's checked at the object-construction level. **When you're reading any
module in this codebase, ask "which mode does this run in, and what happens
when CONNECTED has no data?"** — the answer should always be "explicit missing
state," never "quietly show something else."

## 3. Architecture

```text
apps/web (React 19 + Vite)  ──HTTP──►  backend (FastAPI)  ──►  PostgreSQL
                                              │
                                   SAMPLE provider (real POC data)
                                   CONNECTED provider (stub, not implemented)
                                              │
                                   deterministic scoring / alerts / matching
                                   Monitor (public-signal ingestion pipeline)
                                   Omni (deterministic response composition)
```

### 3.1 Backend layout (`backend/src/btx_omni/`)

| Directory | What's in it |
|---|---|
| `api/` | FastAPI routers — one per surface: `today.py`, `accounts.py`, `intelligence.py`, `map.py`, `actions.py`, `omni.py`, `monitor.py`, `health.py`. `runtime.py` is the composition root (see below). |
| `domain/` | Framework-free dataclasses/enums — the vocabulary of the system (`accounts.py`, `commercial.py`, `alerts.py`, `scores.py`, `work.py`, etc.). No FastAPI or SQLAlchemy imports here by design. |
| `core/` | Cross-cutting governance primitives: `provenance.py`, `classification.py` (PUBLIC / INTERNAL_COMMERCIAL / CONFIDENTIAL / CONTROLLED / **CUI** / **ITAR** / UNKNOWN_REQUIRES_REVIEW — yes, export-control classes, because BTX is aerospace/defense), `policy.py` (deterministic allow/deny for what's eligible to reach a model), `config.py` (env-driven `Settings`). |
| `modules/` | The actual business logic, one package per capability: `scoring/`, `alerts/`, `matching/`, `assistant/` (Omni), `relationships/`, `work/` (Actions), `accounts/`, `intelligence/`, `opportunities/`, `operations/`. |
| `monitor/` | The public-signal ingestion pipeline — normalization, clustering, entity resolution, source registry, durable run tracking. This is its own subsystem with real depth (see §5). |
| `providers/` | `sample/` (the real implementation backing SAMPLE mode), `connected/` (stub), `contracts.py` (the `Protocol` interfaces both must satisfy), plus `hubspot_sample/`, `paperless_sample/`, `lake_sample/`, `research/` — per-source-system SAMPLE shims. |
| `persistence/` | `models.py` (plain SQLAlchemy Core `Table` objects — no ORM classes), database helpers, fixture seeding, durable Monitor candidates, and durable public-Prospect Account reconstruction. |
| `ai/` | A **scaffolded, not-yet-wired** model-provider adapter. See §6 — this is a common point of confusion. |
| `integrations/` | Directories for `hubspot/`, `paperless/`, `prism/`, `public_sources/` — mostly placeholders for real API clients that CONNECTED mode would need. |
| `workers/` | Background-job scaffolding. |

### 3.2 Frontend layout (`apps/web/src/`)

Deliberately flat for a POC — this is a choice, not an oversight:

- `app/App.tsx` — single app shell, no router library visible at top level.
- `api/client.ts` — one HTTP client module for the whole app.
- `features/{today,accounts,intelligence,map,actions,monitor}/` — one `.tsx` +
  one `.css` per surface. No deep component trees, no shared state library
  (no Redux/Zustand in `package.json`).
- `design/`, `components/`, `types/` — shared UI primitives and TS types.

React 19, Vite, TypeScript, `maplibre-gl` for the Tactical Map, Playwright for
e2e (`npm run test:e2e`), a lightweight Node test runner for unit tests
(`node --test tests/*.test.mjs` — not Jest/Vitest).

### 3.3 Composition root

`backend/src/btx_omni/api/runtime.py` — `PocRuntime` is where everything gets
wired together per-process: it builds the `SampleEnvironment`, the
`MonitorService` (with its source registry and optional durable repository),
the optional durable public-Account repository, and the `WorkService`. When durable
state is configured, it composes curated Accounts and durable public Prospects into
one `SampleEnvironment.accounts` collection before existing consumers are built.
Its module docstring states the invariant outright:
*"CONNECTED never falls back to SAMPLE."* This is the one file to read to
understand what gets constructed at startup and in what order.

### 3.4 Database

Plain SQLAlchemy Core (`persistence/models.py`), not the ORM — every table is a
`Table(...)` declaration, domain objects stay framework-free and are mapped
explicitly at repository boundaries. 11 Alembic migrations currently
(`backend/alembic/versions/`, through `0011_durable_public_accounts`). Notable schema pattern: many tables share a
`_truth_columns()` helper (`source_system`, `source_record_id`,
`evidence_state`, `data_mode`, `synthetic`) — the provenance model isn't just
an app-layer concept, it's baked into the schema for every source-shaped
commercial table (`programs`, `commercial_contexts`, `commercial_quotes`,
`orders`, `crm_*`, etc.).

## 4. Walk one path end to end

The fastest way to actually understand this system is to trace one request.
Suggested path: **"a public Monitor observation becomes canonical Intelligence
when — and only when — exact identity and eligibility permit it."**

1. `monitor/sources.py` — a registered source adapter (e.g. `UsaSpendingAdapter`)
   produces raw observations.
2. `monitor/normalization.py` + `monitor/resolution.py` — raw observations get
   normalized and resolved against known accounts/programs. Unresolved stays
   `UNRESOLVED`, not silently dropped or force-matched.
3. `monitor/policy.py` + `monitor/service.py` — only resolved, seller-eligible
   events project as live canonical Intelligence. The durable repository preserves
   events and rehydrates them after restart; duplicate recollection is idempotent.
   Unresolved, ambiguous, and rejected observations remain excluded from seller
   Intelligence.
4. A net-new exact-unresolved organization may become a durable
   `OrganizationCandidate`; explicitly named unresolved program evidence may become
   a `ProgramCandidate`. Both are review-only and do not create Accounts or Programs.
5. `api/intelligence_projection.py` — combines curated public Intelligence with
   eligible rehydrated Monitor events for seller-facing consumers.
6. `modules/alerts/commercial.py` — `CommercialAlertEngine.evaluate()`. This
   is a good file to read start-to-finish: it's ~90 lines, entirely rule-based
   (fixed thresholds as class attributes: `inactivity_days = 90`,
   `bookings_decline_ratio = 0.25`, etc.), and every alert it emits carries its
   `actual` value, its `threshold`, and its evidence IDs. No ML, no
   probabilistic ranking — just explicit comparisons.
7. `modules/scoring/account_attractiveness.py` — `calculate_account_attractiveness()`.
   Six weighted factors (`FACTORS` tuple, weights sum to 1.00), each with
   sub-factor rubrics. Missing data reduces `coverage` and is reported
   explicitly (`missing_subfactors`) rather than defaulting to a neutral score.
   Monitor/public Intelligence currently does **not** derive score inputs: there is
   no approved public-Intelligence-to-factor policy. The service only consumes
   existing governed SAMPLE scoring inputs.
8. `api/today.py` / `api/accounts.py` — surfaces the result.
9. `modules/work/service.py` — if a seller acts on it, `WorkService` creates a
   session-only work item with an idempotency key. Per
   `SELLER_POC_OPERATION.md`: *"Actions and audit events are held only in API
   process memory and reset on a restart; they are not durable PostgreSQL
   workflow records yet."* — worth confirming that's still true when you read
   the code; it's the kind of detail that changes with the codebase's pace.

## 5. Six things that are easy to get wrong about this codebase

These are the non-obvious facts that took direct code reading (not just the
README) to confirm. A reviewer should know all six before forming opinions.

1. **Omni resolves governed application truth before optional model synthesis.**
   `modules/assistant/orchestration.py` retains deterministic typed routing;
   `modules/assistant/service.py` invokes it through an allow-listed read tool,
   then optionally asks the server-side Gemini adapter to organize the completed
   answer. Missing configuration, timeout, or malformed provider output returns
   the deterministic answer. Provider code cannot mutate Actions, CRM, SQL, or
   canonical context.
   The browser supplies typed surface, selected-entity, filter, and visible-record
   context; `context_used` and the bounded `conversation_referent` are structured
   contract data, not semantics inferred from assistant prose.
2. **Actions are durable and backend-authorized.** Omni receives only the
   principal-filtered read projection and has no mutation tool.
3. **CONNECTED mode fails closed by raising an HTTP 503**, not by silently
   substituting SAMPLE data. This is enforced in `PocRuntime.environment()`,
   not just documented.
4. **The classification enum includes ITAR and CUI** — export-control
   categories — because BTX is an aerospace/defense manufacturer. Domain data
   with those classifications is architecturally excluded from model context
   by `core/policy.py::model_context_policy()`, independent of whether a model
   call ever fires.
5. **Frontend has no state-management library** and a flat one-file-per-surface
   structure. This is appropriate for the POC's current scope, but is worth
   discussing with the team if/when the surfaces grow — it's a scaling
   question, not a defect.
6. **Candidates and durable Prospects are foundations, not automatic promotion.**
   Monitor can persist exact-unresolved `OrganizationCandidate` and explicit
   `ProgramCandidate` evidence. The runtime can also compose a durable canonical
   public `PROSPECT` Account. There is no governed Candidate → Account promotion
   command yet, Program Candidates are not promoted, and no candidate gets a score,
   customer history, CRM record, or inferred geography.
7. **Relationship Intelligence is bounded and read-only.** Its Account 360 views
   render only canonical direct or service-returned bounded-path edges, retaining
   direction, validation, and per-hop public/SAMPLE provenance. They do not infer
   relationship strength, warm paths, introductions, or new edges; Omni uses the
   same canonical relationship path rather than UI adjacency as authority.

## 6. Design decisions and the reasoning behind them

| Decision | Why |
|---|---|
| Deterministic scoring/alerts instead of ML | The product's core trust claim is "every score/alert is explainable and reproducible." A fixed-weight rubric with explicit missing-data handling is auditable in a way a trained model isn't, and this is a governed B2B sales context where a seller needs to defend *why* an account is prioritized. |
| SAMPLE never falls back to CONNECTED-shaped confidence, and CONNECTED never falls back to SAMPLE | Prevents the two most dangerous failure modes for a "trust the data" product: showing fake data as real, or silently degrading real data to fake without saying so. |
| `Provenance` as a mandatory field on governed facts, enforced via dataclass invariants | Makes "where did this come from and can I trust it" a compile/construct-time property instead of a documentation convention that will drift. |
| Domain layer is framework-free (no FastAPI/SQLAlchemy imports in `domain/`) | Keeps business vocabulary testable and portable independent of the web/persistence layers; `persistence/repository.py` is the explicit mapping boundary. |
| `providers/contracts.py` uses `Protocol`, not ABC inheritance | SAMPLE and (eventually) CONNECTED providers satisfy the same structural interface without a shared base class — lower coupling, easier to add a third provider later. |
| Omni is deterministic-first with a model adapter as an unused extension point | Ships a working, explainable assistant now without taking on model-provider approval, cost, or non-determinism risk before BTX has signed off on that (see `docs/product/SELLER_POC_OPERATION.md`). |
| Public Monitor evidence is not a scoring input by itself | The Account Attractiveness rubric remains the single authority over existing governed SAMPLE inputs. There is no approved public-Intelligence-to-factor derivation policy, so Monitor never assigns points or changes a score. |
| Durable public Prospects compose into the canonical runtime universe | A durable Account carries complete public identity/provenance and is composed with curated Accounts at the runtime boundary; it remains unscored and has no commercial history unless a later governed process supplies it. |
| No autonomous CRM writes anywhere in the system | Explicit product/legal boundary — every write path requires a human confirmation step, enforced in `modules/work/`. |
| Plain SQLAlchemy Core instead of the ORM | Keeps the schema declarative and explicit (`persistence/models.py` is literally readable top to bottom) without ORM relationship/session lifecycle complexity for what is currently a read-heavy POC. |

## 7. Tests

`backend/tests/` — 24 files, notably including `test_account_attractiveness.py`,
`test_commercial_alerts.py`, `test_intelligence_matching.py`,
`test_monitor*.py` (including durable event/candidate coverage),
`test_durable_public_accounts.py`, `test_poc_contracts.py`,
`test_sample_provider_foundation.py`, `test_seller_scenario_semantics.py`. CI
(`.github/workflows/ci.yml`) runs `ruff check`, `pytest`, an Alembic
upgrade/current check, and an OpenAPI-schema sanity check on every PR and push
to `main`, plus `typecheck` / `lint` / `test` / `build` for the frontend.
Frontend also has a Playwright e2e suite (`npm run test:e2e`), which CI does
not currently run — worth asking about.

## 8. Known limitations (from the README, worth re-verifying against current code)

- PRISM/PowerBI, Paperless Parts, and HubSpot production access are all
  deferred — SAMPLE data shapes what these *would* return, unconfirmed against
  real schemas.
- Okta/enterprise SSO deferred; development auth only.
- No live public-source collectors wired for scheduled/automatic runs — Monitor
  collection is a protected manual operator call only, gated by
  `BTX_MONITOR_OPERATOR_TOKEN` and `BTX_MONITOR_MODE=live`.
- No approved public-Intelligence → Account Attractiveness factor derivation
  policy. Eligible public events remain Intelligence; they do not change scores.
- Organization/Program Candidate persistence and durable canonical
  public-Prospect Account/Program composition exist. Human-governed Candidate
  and Program Candidate promotion are implemented only through explicit,
  confirmed server-side commands with final exact conflict checks; Monitor
  collection never promotes automatically. Public-Intelligence scoring policy
  and seller-visible greenfield prioritization remain deferred.
- External Top 100 ranking authority/data is unresolved; no Top 100 Map layer is
  implemented. Component-type Map filtering remains deferred.
- MapLibre remains the map engine. A canonical Account receives no Map pin without
  a verified facility; public-event geography is never inferred.
- Local PostgreSQL availability is an environment concern, not a guaranteed POC
  runtime state. Isolated durable SQLite tests prove persistence behavior without
  claiming a local PostgreSQL service is running.
- Overdue-order alerts are architecturally supported
  (`CommercialAlertEngine` has the logic) but not enabled — depends on
  order-level PRISM fields BTX hasn't confirmed yet.

## 9. Suggested reading order for the reviewer

1. This doc.
2. `README.md` (root) — the product-level framing.
3. `backend/src/btx_omni/core/provenance.py`, `classification.py`,
   `domain/common.py` — the vocabulary everything else builds on.
4. `backend/src/btx_omni/api/runtime.py` — how it all gets wired at startup.
5. `backend/src/btx_omni/monitor/candidates.py`,
   `backend/src/btx_omni/monitor/promotion.py`, and
   `backend/src/btx_omni/persistence/durable_accounts.py` — governed candidate
   review/promotion and durable canonical-Prospect foundations.
6. `backend/src/btx_omni/modules/alerts/commercial.py` — small, self-contained,
   good example of the deterministic-rules pattern used throughout.
7. `backend/src/btx_omni/modules/assistant/orchestration.py` — the biggest
   file in the repo; skim rather than read line-by-line first.
8. `docs/product/POC_CAPABILITY_MANIFEST.md` and
   `docs/product/SURFACE_CONTRACTS.md` — the authoritative capability/route
   contracts.
9. `backend/tests/test_poc_contracts.py` — what the team considers load-bearing
   enough to pin with tests.
