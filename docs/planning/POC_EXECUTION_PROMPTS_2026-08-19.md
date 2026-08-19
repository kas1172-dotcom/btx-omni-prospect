# BTX Omni Prospect — POC Execution Prompt Pack (Reviewed)

## Purpose

This document supersedes the draft prompt pack reviewed on 2026-08-19. It carries
the same intent — a checkpoint-by-checkpoint execution sequence for Codex — with
corrections applied from a direct inspection of the repository's actual git state,
migration chain, and branch/PR landscape (not just the draft's self-reported state).

Do not assume every prompt below still needs to be executed by the time this is
read again. Re-verify "Current known state" before starting, the same way this
review did — states drift fast in this repo.

---

## Current known state (verified 2026-08-19)

The prior draft understated the actual scope of uncommitted work. Verified directly:

- **Working tree diff vs. the last shared merge (`49882f5`, PR #2): 108 files
  changed, 16,957 insertions, 10,442 deletions.** This is not "markets.py +
  migration 0009." It also touches `api/map.py`, `api/monitor.py`,
  `api/accounts.py`, `domain/accounts.py`, `domain/btx.py`,
  `modules/assistant/orchestration.py`, `monitor/sources.py`,
  `monitor/usaspending.py`, `monitor/packs/__init__.py`,
  `persistence/models.py`, `providers/research/*`, `providers/sample/environment.py`,
  most of `docs/`, and the core `docs/research/*.json` files.
- **Branch: `checkpoint/pre-reconciliation-2026-08-17`, HEAD: `645e518`.** This
  branch has **never been pushed** — it has no `origin/` counterpart. That
  matters directly for Prompt 0B: there is no shared/deployed environment that
  could be corrupted by history changes on this branch, only the local dev DB.
- **Migration chain 0005→0009 is internally consistent**: verified every
  `revision`/`down_revision` pair by hand, no gaps or forks. `0006`/`0007` were
  first committed in `99ee223` (already part of this branch's history, not a
  fresh uncommitted invention) and are written defensively (`if column not in
  existing_columns`), so re-running upgrade against a DB that already has an
  earlier form of these tables should not fail.
- **Branch landscape is larger than previously described.** Full inventory:
  - Local: `main`, `checkpoint/pre-reconciliation-2026-08-17` (current),
    `feature/monitor-2-architecture`, `recovery/checkpoints-13-21`,
    `release/poc-convergence`, `release/poc-final-integration`,
    `safety/pre-recovery-20260816-204439`, `backup/local-main-44914c1`.
  - Remote (`origin`): `main`, `feature/monitor-2-live-sources`,
    `release/poc-convergence`, `release/poc-final-integration`.
  - `feature/monitor-2-architecture`, `recovery/checkpoints-13-21`, and
    `release/poc-final-integration` have **zero commits not already in `main`**
    — clean, safe to delete once Phase 0C confirms this again.
  - `safety/pre-recovery-20260816-204439` and `backup/local-main-44914c1` each
    carry exactly one unique commit, `e7cc081` ("fix(deploy): normalize Fly
    Postgres URL for psycopg") — **the same fix, by title, already merged to
    `main` as `35335bd`** via PR #2.
- **PR #3** (`release/poc-convergence` → `main`) **is open and reports
  `mergeable: CONFLICTING`.** Its single commit is `e7cc081` — the same
  redundant fix described above. It is very likely safe to close without
  merging, but Phase 0C must confirm the `core/config.py`/`fly.toml` diffs are
  equivalent to what's already in `main` before closing it.
- **There is a second git worktree**: `btx-omni-prospect-recovered-validation`,
  checked out on `release/poc-final-integration`. The branch itself has no
  unique commits, but the worktree's own working-tree state has not been
  inspected and must be before Phase 0C is considered complete.

The six current BTX primary markets are unchanged:

1. Aerospace
2. Defense
3. Semiconductor
4. Space Exploration
5. Energy
6. Medical

Robotics may remain as a secondary classification/capability where useful but is
not one of the six canonical BTX primary markets.

### Phase 1 (already implemented — retained for architectural context)

The reported SAMPLE environment counts (34 researched companies, 29 commercial
contexts, 92 quotes, 41 orders, 31 CRM companies, 48 CRM contacts, 43 CRM deals,
43 CRM activities, 35 relationship edges, 12 golden scenarios) are consistent
with what's on disk. What the original draft did not disclose is that this same
body of work already reaches into Monitor, Map, Accounts API, and Omni
orchestration files that Phases 2–6 below assume they are approaching fresh —
each of those phases now opens with an explicit step to review what Phase 1
already changed in its territory before writing anything new.

Reported test/build results (22 targeted tests, 77 backend tests, clean SQLite
migration to `0009`, frontend typecheck/lint/tests/build, `git diff --check`)
were not re-run as part of this review and should be re-verified at the start
of Phase 0A, not assumed current.

---

## Global POC principles

Unchanged from the original draft — these were sound and are retained verbatim
in intent.

### Data truth model

Use real researched entities wherever the external-world entity is knowable
(companies, public facilities, public programs, verified public contacts,
public contracts, public awards, public relationships, monitor intelligence).

Simulate only BTX-internal facts not yet accessible (Prism-like revenue,
bookings, order history, backlog, Paperless Parts quoting, HubSpot internal
state, BTX ownership, internal seller activity, internal commercial outcomes,
capacity proxies where unavailable).

SAMPLE mode does not imply every record is synthetic:

```
researched public fact  → data_mode = SAMPLE, synthetic = false
simulated BTX fact      → data_mode = SAMPLE, synthetic = true
```

Preserve provenance and evidence-state rigor throughout the system. (Confirmed
this maps directly onto the existing `Provenance` dataclass and
`DataMode`/`EvidenceState` enums in `backend/src/btx_omni/core/provenance.py`
and `domain/common.py` — no new vocabulary needed.)

### Global implementation constraints

Do not:

- create another repository, frontend, backend, or database
- duplicate the domain model
- introduce Neo4j or another graph database for the POC
- redesign the deterministic account-attractiveness score unless explicitly instructed
- call live BTX internal systems or use BTX credentials
- fabricate external company identities
- recreate a 600-account universe
- add automatic monitor scheduling yet
- build a large interactive graph explorer
- perform speculative AI-generated relationship inference without evidence
- replace existing architecture merely because a new abstraction appears cleaner

Preserve and extend: provider boundaries; SAMPLE vs CONNECTED semantics;
provenance/evidence handling; canonical IDs; commercial domain model; monitor
architecture; MapLibre; Omni; migration chain; useful acceptance scenarios;
reusable scalable infrastructure.

**New note, added by this review:** the "no large interactive graph explorer"
constraint is in direct tension with the Figma file's "09 — Relationship
Intelligence — Operating Model" reference screen, which describes hover
previews, a click-to-pin inspector, and re-centering on selection — i.e., an
interactive graph. Phase 9B below resolves this explicitly: build the *data
and API* for full traversal (Phase 2), but implement the *screen* as a bounded
list/card view of validated paths ("keep the graph small by default," per the
Figma copy itself), not a pannable canvas. Do not let Codex choose either
extreme without this framing.

---

## PHASE 0 — SOURCE-CONTROL AND MIGRATION RECONCILIATION

### Prompt 0A — Checkpoint Phase 1 safely

You are working in the existing BTX Omni Prospect repository, branch
`checkpoint/pre-reconciliation-2026-08-17`, HEAD `645e518`, working tree not
clean.

Do not begin new feature work.

**Requirements**

1. Inspect the entire working-tree diff — expect roughly 108 files, ~17k
   insertions, ~10k deletions. Confirm this matches current reality; report the
   real number, not an assumed one.
2. Identify every modified and untracked file. Group them explicitly by
   subsystem (sample/provider, API, domain, monitor, map, assistant,
   persistence, tests, docs, research JSON) so later phases can see at a glance
   what Phase 1 already touched in their territory.
3. Verify every change belongs to the Phase 1 implementation or is an
   intentional prerequisite. Pay special attention to:
   - `markets.py` (new)
   - migration `0009_btx_facility_location_metadata` (new)
   - modifications to migrations `0006`/`0007` (already-committed-history edits — see Prompt 0B)
   - `api/map.py`, `api/monitor.py`, `api/accounts.py` — confirm these changes are Phase-1-appropriate (sample-data plumbing) and not accidental scope creep into Phase 3/4/5 territory
   - `modules/assistant/orchestration.py` — same check against Phase 6
   - sample environment/provider changes
   - tests
   - research manifests
   - documentation
4. Do not silently discard unrelated valuable changes.
5. Re-run the previously reported verification (targeted tests, full backend
   suite, frontend typecheck/lint/tests/build, `git diff --check`) — do not
   assume the prior report is still accurate.
6. Create one local checkpoint commit containing the complete validated Phase 1
   state.
7. Do not push, merge, or deploy.

**Report**

Return: branch; original HEAD; new checkpoint commit; files included (grouped
by subsystem per requirement 2); files intentionally excluded; test results;
resulting working-tree status.

---

### Prompt 0B — Audit historical migration modifications

Inspect the modifications to Alembic revisions `0006` and `0007`.

**Already established by this review** (re-verify, don't re-derive from
scratch): the chain `0005_monitor_live → 0006_monitor_durable_events →
0007_usaspending_relevance_state → 0008_commercial_and_edges →
0009_btx_facility_location_metadata` is internally consistent with no gaps or
forks. `0006`/`0007` were first committed in `99ee223`, which is local-only —
this branch has never been pushed to `origin`. Both files already guard
column-add operations with `if column not in existing_columns` checks.

**Questions to answer**

1. Confirm the branch is still unpushed (`git log origin/main..HEAD` /
   equivalent) — if it has since been pushed or shared, the risk calculus
   changes and this prompt's conclusion must be revisited.
2. Has the *local* dev database (SQLite, per the Phase 1 report) already run
   an upgrade through `0006`/`0007` in an earlier form, before the current
   edits? If so, does re-running upgrade against that same DB succeed cleanly
   given the defensive guards, or does it need a manual reset?
3. Are the `0006`/`0007` changes semantic changes to migration *history*, or
   defensive/idempotency fixes only? (Read the diff — this review found them
   to be defensive only, but confirm against the current diff, which may have
   moved on.)
4. Does `0008` depend on any modified behavior in `0006`/`0007`? (Verified: no
   — `0008`'s `down_revision` cleanly points to `0007`, and `0008` does not
   reference the specific columns `0006`/`0007` add.)
5. Are upgrade/downgrade/re-upgrade paths still safe on both SQLite and
   Postgres?

**Verification**

Test: clean upgrade; current; downgrade/re-upgrade where supported; schema
integrity on both SQLite and Postgres.

**Return a clear recommendation before moving on** — expected conclusion,
pending re-verification: low risk, proceed, no forward-migration rework
needed.

---

### Prompt 0C — Reconcile all branches, PRs, worktrees, stashes, and unique commits

Do not perform product feature development during this checkpoint.

**Known state — use this as a starting inventory, then re-verify, don't
re-derive from scratch:**

| Branch | Unique commits vs. `main` | Disposition (pending re-confirmation) |
|---|---|---|
| `feature/monitor-2-architecture` | 0 | Safe to delete |
| `recovery/checkpoints-13-21` | 0 | Safe to delete |
| `release/poc-final-integration` | 0 (fully merged via PR #2) | Safe to delete |
| `safety/pre-recovery-20260816-204439` | 1 (`e7cc081`) | Likely redundant with `35335bd` on `main` — confirm via diff, then delete |
| `backup/local-main-44914c1` | 2 (merge bubble + `e7cc081`) | Likely redundant, same as above — confirm via diff, then delete |
| `release/poc-convergence` | 1 (`e7cc081`, same commit as above) | Open PR #3, `mergeable: CONFLICTING` — see below |

**Open PR #3** (`release/poc-convergence` → `main`): single commit `e7cc081`
("fix(deploy): normalize Fly Postgres URL for psycopg"), touching
`backend/.env.example`, `backend/src/btx_omni/core/config.py`,
`backend/tests/test_config.py`, `fly.toml`. This is almost certainly superseded
by `35335bd`, already on `main` via PR #2, which addresses the same problem.
**Diff the two commits' changes to `core/config.py` and `fly.toml` directly.**
If equivalent (expected), close PR #3 without merging and record why. If *not*
equivalent — e.g. the two fixes solve the problem differently and one is
better — cherry-pick the delta into `main` deliberately rather than merging a
conflicting branch wholesale.

**There is a second worktree** at `btx-omni-prospect-recovered-validation`
(branch `release/poc-final-integration`, 0 unique commits vs. `main`). Inspect
its own working-tree status independently — the branch being fully merged
does not guarantee that worktree's checkout is clean.

**Inventory everything** (as originally scoped): local branches, remote
branches, tracking relationships, `git status`, `git log --all`, ahead/behind
state, worktrees, stashes, unmerged commits, tags if relevant, open PRs,
closed-but-unmerged PRs if any, local-only commits, commits not reachable from
the intended baseline.

**Classification.** For every branch containing unique commits, classify its
unique work as: already incorporated / still valid and must be preserved /
superseded by newer implementation / obsolete and safe to retire. Do not
blindly merge branches — compare content and architectural intent, the way
this review compared `e7cc081` against `35335bd` rather than trusting the
branch name.

**Merge/reconciliation strategy.** Create one authoritative development
baseline containing all currently valid work (this should end up being the
Phase 0A checkpoint commit on `checkpoint/pre-reconciliation-2026-08-17`,
since it is the superset). Resolve conflicts deliberately. Do not delete a
branch until its unique commits have been accounted for.

**Verification after reconciliation.** Run: Alembic heads; clean migration
upgrade/current; backend targeted tests; full backend tests; frontend
typecheck; frontend lint; frontend tests; frontend production build; `git diff
--check`.

**Final report.** Return: branch inventory; unique work per branch; the actual
diff-based disposition decisions (not name-based assumptions); PR #3 status
and disposition; second-worktree findings; authoritative baseline (branch +
HEAD); test results; remaining source-control risks.

The checkpoint is not complete until no useful work is known to be stranded
elsewhere, and until PR #3 and the second worktree are explicitly resolved
(not silently ignored).

---

## PHASE 1 — REAL-COMPANY SAMPLE ENVIRONMENT

Status: already implemented. Retained for architectural review context only —
see "Current known state" above for what this review found about its actual
diff footprint.

Desired result (unchanged): the POC contains whatever researched real
companies are actually available; no artificial target population exists; no
exactly-600, no exactly-100-per-industry, no filler companies, no artificial
map geography, no population-dependent scoring.

Current reported result (unchanged pending Phase 0A re-verification): 34
companies across the six primary markets (Aerospace 6, Defense 12,
Semiconductor 6, Space Exploration 8, Energy 4, Medical 6; multi-market
membership allowed); Symbotic outside the six with Robotics as secondary; 29
commercial contexts, 92 quotes, 41 orders, 31 CRM companies, 48 CRM contacts,
43 CRM deals, 43 CRM activities, 35 relationship edges, 12 golden scenarios,
all resolving without orphan IDs.

---

## PHASE 2 — RELATIONSHIP INTELLIGENCE FOUNDATION

### Prompt 2 — Harden the existing relationship-intelligence foundation

Continuing from the reconciled baseline (Phase 0 complete).

Do not create a separate graph product. Do not introduce Neo4j.

**New first step, added by this review:** before inspecting the architecture
in the abstract, diff exactly what Phase 1 already changed in
`domain/accounts.py` and `domain/btx.py` — these were already modified in the
Phase 1 working tree and Phase 0A's checkpoint will have baked those changes
in. Understand what's already there before adding to it, so this phase doesn't
silently revert or duplicate Phase 1 work.

**Also read `docs/audit/AUDIT_2026-08-17.md` §8 before designing anything.**
That section already proposes a concrete relationship-edge data model and API
shape (`GET /accounts/{id}/relationships`, `GET /relationships/matrix`). Use
it as the starting design, not a blank page — deviate only where the existing
`AccountRelationshipEdge` dataclass (`domain/relationships.py`: `id`,
`from_account_id`, `to_account_id`, `edge_type`, `direction`, `strength`,
`evidence_state`, `source_ids`, `narrative`, `program_id`, `provenance`) forces
a difference.

First inspect the existing architecture: relationship domain models; edge
persistence; sample relationship fixtures; relationship API surfaces
(**confirmed currently: none — `relationship_edges` is loaded into
`SampleEnvironment` but zero routers read it**); services consuming
relationships; relationship-related tests; commercial tables from recent
migrations; program/account/facility/contact/capability models. Avoid
duplicating existing capabilities.

**Required entity relationships** (unchanged from draft): Account→Account,
Account→Contact, Account→Facility, Account→Program, Account→BTX Business Unit,
Account→Quote, Account→Order, Program→Intelligence Event,
Program→Component Class, BTX Business Unit→Capability.

**Relevant relationship types** (unchanged): `PARENT_OF`, `SUBSIDIARY_OF`,
`PRIME_ON`, `SUPPLIER_TO`, `PARTICIPATES_IN`, `OPERATES`, `HAS_CONTACT`,
`QUOTED_WITH`, `ORDERED_WITH`, `CUSTOMER_OF`, `RELATED_TO_PROGRAM`,
`CAPABILITY_MATCH`, `SHARED_PROGRAM`, `SHARED_PRIME`. Use naming that fits
existing conventions. Do not add every hypothetical type merely for
completeness.

**Evidence and provenance** (unchanged): source entity, target entity,
relationship type, provenance/evidence reference, evidence state, observed
timestamp, valid-from/valid-to when meaningful, SAMPLE/CONNECTED distinction.
Do not treat inferred public relationships as confirmed BTX internal facts.

**Traversal capability** (unchanged): support
`Company → Program → Component Class → Capability → BTX Business Unit →
Quote/Order/Commercial History` and
`Intelligence Event → Program → Account → Relevant BTX relationship`. Keep
traversal bounded and understandable. Do not implement generalized arbitrary
graph algorithms.

**SAMPLE data**: reconcile the existing 35 edges with the richer relationship
model. Preserve useful existing relationships. Add only enough depth to
support the golden POC scenarios. Do not manufacture large networks for scale.

**API/service usage**: expose relationship intelligence in reusable backend
services, consumable by Account Detail, Intelligence, scoring/workflows,
Omni, and Map context. **Do not build a dedicated graph visualization UI here**
— that's Phase 9B's job, and it's bounded there explicitly (see the tension
noted in Global Implementation Constraints above).

**Testing**: valid source/target entities; provenance semantics; duplicate-edge
handling; basic traversal; account→program→capability path;
intelligence→account/program relationship path; SAMPLE vs real-public
distinction; missing/conflicting relationship evidence.

Run: targeted relationship tests; commercial tests; full backend tests;
migrations; frontend verification if contracts changed.

**Final report**: relationship models changed; edge types supported; existing
edges retained; new edges added; traversal services; API changes (including
confirmation the two audit-proposed endpoints now exist); tests; remaining
limitations.

---

## PHASE 3 — MONITOR 2.0 CORRECTION AND LIVE MANUAL VALIDATION

### Prompt 3 — Finish Monitor 2.0 for the six BTX markets

The monitor does not need automatic scheduling yet, but must be easy to
schedule later using the exact same runner.

**New first step, added by this review:** `monitor/sources.py`,
`monitor/usaspending.py`, `monitor/packs/__init__.py`, and `api/monitor.py`
were already modified in the Phase 1 working tree. Diff what's already there
before starting — this phase is hardening/finishing existing Phase 1 monitor
work, not greenfield.

Canonical markets (unchanged): Aerospace, Defense, Semiconductor, Space
Exploration, Energy, Medical. Robotics may remain a secondary
keyword/capability. Remove obsolete primary-market assumptions; centralize
taxonomy (this should now flow through the new `domain/markets.py`
`PRIMARY_MARKETS` frozenset rather than being redefined ad hoc — confirm
`monitor/*` actually imports from there rather than duplicating the list).

**Audit current monitor sources**: for each source/provider determine live vs.
placeholder, enabled vs. disabled, auth requirements, time-window behavior,
market applicability, current health, duplicate overlap, evidence/provenance
support. Do not keep broken integrations merely to inflate source count.

**Source coverage** (unchanged): SAM.gov, USAspending, Federal Register, NASA,
FDA/openFDA where relevant, SEC/company filings, official company newsrooms,
relevant federal agency procurement/award sources, authoritative
industry-specific sources. Source selection may differ by industry.

**Freshness** (unchanged): explicit recency rules; every event preserves
source, source URL, publication/event date, retrieval date, market, event
type, company/account candidate, program candidate where relevant, provenance,
evidence state, relevance score/rationale where applicable. Avoid broad date
windows surfacing old records as current.

**Relevance filtering** (unchanged): distinguish commercially meaningful BTX
intelligence (contract award, production expansion, new facility, capacity
expansion, defense procurement, fab investment, supply-chain disruption,
acquisition, program milestone) from noise (charity events, executive
lifestyle content, generic marketing, unrelated consumer news, resurfaced old
press releases). Deterministic filtering/ranking wherever practical; AI may
assist ambiguous unstructured evidence but should not replace source-grounded
facts.

**Entity resolution, deduplication, manual runner, persistence** (unchanged
from draft — see original phrasing, still correct): resolve event→company,
event→program, event→facility using canonical IDs, preserving unresolved
candidates rather than forcing incorrect matches; cluster/link duplicate
events across sources without uncontrolled duplicate seller alerts; one
canonical execution entry point (manual run → runner → provider collection →
normalization → dedup → classification → persistence → intelligence
availability), no separate scheduled logic; persist to the existing database
architecture, not in-memory only.

**Run the monitor live** against currently supported public sources (no BTX
internal systems). Inspect results for every one of the six markets; record
representative events; assess each for recency, relevance, correct
market/company/program, duplication, evidence backing, seller usefulness.

**Benchmark**: create a small maintainable monitor evaluation
artifact/fixture — foundation for regression checking, not a QA framework.

**Acceptance requirement**: a successful HTTP response is not acceptance. The
checkpoint succeeds only if actual retrieved events are recent and materially
useful to a BTX seller across the required markets.

**Final report**: sources audited/enabled/disabled and why; recency logic;
persistence changes; market coverage; live run results; representative events
by market; relevance findings; known gaps; exact manual execution command; how
a scheduler could later invoke the same runner; tests.

---

## PHASE 4 — MAPLIBRE FUNCTIONAL COMPLETION

### Prompt 4 — Make the MapLibre experience fully functional

Do not perform final Figma styling yet — focus on functional correctness.

**New first step, added by this review:** `api/map.py` was already modified
in the Phase 1 working tree. Diff what's there before changing it.

Audit current implementation: map initialization; styles/tiles; GeoJSON
sources; layers; clustering; marker rendering; backend map APIs; account
data; facility data; intelligence coordinates; selected-account interaction;
filters; resize behavior. Identify any mock/stub behavior.

**Required geographic entities** (unchanged): researched companies with known
location; researched company facilities; BTX facilities; monitor intelligence
with coordinates; relevant geographic events/program locations where
appropriate. Do not generate fake coordinates to make the map look populated.

**Known issue: dynamic GeoJSON updates.** Ensure backend/API data changes →
frontend records change → existing MapLibre GeoJSON source receives
`setData(...)`, without requiring full map reinitialization for normal
updates.

**Known issue: intelligence markers.** Trace the complete path — monitor/
backend coordinate → API DTO → frontend model → GeoJSON feature → MapLibre
source → visible rendered marker. Ensure coordinates are not discarded or
converted to `geometry: null`.

**Interactions to verify** (unchanged from draft): initial load, basemap
render, zoom, pan, clusters, cluster expansion, account selection, facility
selection if designed, intelligence markers, linked-intelligence toggle,
market filters, selected account state, navigation from map to account,
resize/viewport changes, loading, empty state, backend failure, missing
coordinates, invalid coordinates.

**Backend/frontend contracts**: make map contracts explicit and typed.
Canonical backend data should drive the map, not UI-specific fabrication.

**Tests**: map API contracts; GeoJSON conversion; intelligence coordinate
preservation; facility coordinate preservation; account selection; filter
behavior; dynamic source updates where testable. Run backend map/API tests,
frontend tests, typecheck, lint, production build.

**Manual acceptance**: launch the app; confirm a human user can actually see
and interact with the map; include clear run instructions in the report.

**Final report**: map architecture; bugs fixed; entities rendered;
marker/layer types; clustering behavior; intelligence rendering; dynamic
update behavior; manual run steps; tests; remaining visual differences to
Figma.

---

## PHASE 5 — BACKEND/FRONTEND CONTRACTS, SCORING, AND WORKFLOW INTEGRITY

### Prompt 5 — Align product surfaces with canonical backend behavior

Do not perform final visual Figma implementation yet.

**New first step, added by this review:** `api/accounts.py` was already
modified in the Phase 1 working tree. Diff what's there before changing it.

Audit product surfaces (Today, Accounts, Account Detail, Intelligence, Map,
Actions/workflows, Omni integration points): for every displayed field,
determine its backend source; for every important backend concept, determine
whether it's intentionally visible, intentionally background-only, or
currently missing from the UI. Do not create duplicate frontend-derived truth.

**Account attractiveness scoring**: do not redesign the rubric. Verify the
existing deterministic score exactly as intended — factor weights, point
rules, threshold rules, missing-data behavior, conflicting-data behavior,
quote history, win/loss history, revenue/bookings, order history, capacity
proxy, customer relationship, program/capability match, relevant cross-BU
context, recency, evidence/provenance for score inputs. Ensure the score no
longer relies on obsolete fixed-population assumptions.

**Separate score from rank**: the deterministic score should not depend on
how many POC companies happen to be loaded. If rank is shown, define it
explicitly as "rank among currently eligible loaded accounts" — do not
conflate with an external Top-100 ranking or with the score itself.

**Workflow integration**: exercise external intelligence → resolve
account/program → relationship traversal → commercial-context retrieval →
deterministic score → alert/work item → Today → Account Detail → seller
action.

**Negative scenarios** (unchanged): irrelevant event; duplicate event;
unresolved company; unresolved program; missing internal history; conflicting
evidence; stale quote; dormant customer; no previous BTX relationship;
multiple relevant BTX business units.

**Data provenance**: every meaningful seller-facing fact (revenue, bookings,
quote status, order history, alert, opportunity score, program relationship,
intelligence event, capacity proxy) should be traceable. Do not allow
synthetic commercial data to appear BTX-confirmed.

**APIs**: ensure frontend/backend DTOs are coherent for account summaries,
account detail, intelligence, scoring explanation, relationship summaries,
actions, map data. Remove unnecessary compatibility hacks that only serve
obsolete fixtures if safe to do so.

**Verification**: scoring tests; commercial tests; workflow tests; account
API tests; intelligence tests; relationship tests; map tests; full backend
suite; frontend typecheck; lint; tests; build.

**Final report**: product surfaces audited; contract mismatches fixed; scoring
verification; workflow scenarios passing; negative scenarios; remaining UI
gaps; tests.

---

## PHASE 6 — OMNI AS THE OS INTERFACE

### Prompt 6 — Finish Omni's contextual OS behavior

Omni should feel "always aware, never in the way" — not a generic chatbot
attached to a CRM. Do not perform final visual styling yet.

**New first step, added by this review:** `modules/assistant/orchestration.py`
was already modified in the Phase 1 working tree, and the `POST /omni`
endpoint already accepts `account_id`, `question`, and a `context` field —
confirm the existing `context` field's shape before designing a new envelope;
extend it rather than replacing it if it already fits.

**Remove hard account dependency**: Omni should accept questions with no
account selected — contextual ("Why is this account attractive?"), screen
("What matters most on this page?"), cross-product ("Which Defense accounts
have open quotes?"), and arbitrary free-form questions. The user must never be
trapped by the current screen or selected entity.

**Structured UI context**: a minimal envelope — `current_surface`,
`selected_account_id`, `selected_program_id`, `selected_event_id`,
`selected_facility_id`, `active_filters`, `visible_record_ids`,
`navigation_context`. Do not send the entire DOM; do not make Omni dependent
on fragile visual scraping.

**Context priority**: current context should assist interpretation of
ambiguous requests, not constrain the user from asking about unrelated
subjects.

**Relationship intelligence**: allow Omni to traverse canonical relationships
(event → program → company → component/capability → BTX business unit →
quote/order/commercial history) once Phase 2's traversal service exists. Do
not hallucinate missing edges.

**Evidence states**: Omni should correctly distinguish confirmed / inferred /
missing / conflicting, and real public evidence vs. simulated SAMPLE
commercial context. Language must make SAMPLE status clear where materially
relevant.

**Reasoning and actions**: expanded Omni may expose answer, evidence,
reasoning summary, suggested next actions. No constant intrusive context
banners; collapsed Omni stays minimal.

**Tool boundaries**: deterministic and source-grounded for POC-critical
facts. No autonomous write actions unless explicitly required. No
production-system writes. No unbounded live research agent unless separately
designed.

**Tests**: question without selected account; account-context question;
screen-context question; cross-account query; relationship traversal; missing
evidence; conflicting evidence; SAMPLE disclosure; arbitrary unrelated
question path; context switching; stale context prevention. Run Omni backend
tests, frontend Omni tests, full backend suite, frontend verification.

**Final report**: context envelope (and whether it extended or replaced the
existing `context` field); backend changes; supported query categories;
relationship integration; evidence behavior; remaining limitations; tests.

---

## PHASE 7 — FUNCTIONAL END-TO-END POC ACCEPTANCE

### Prompt 7 — Run full functional seller-scenario acceptance

Do not redesign the architecture during this checkpoint unless a blocking
defect is discovered.

**Scenarios A–I are unchanged from the original draft:**

- **A** — External opportunity: real recent intelligence event → monitor →
  canonical event → company resolution → program resolution → relationship
  traversal → synthetic BTX commercial context → deterministic score →
  alert/work item → Today → Account → Map where relevant → Omni explanation →
  seller action.
- **B** — Dormant-customer reactivation.
- **C** — Cross-BU opportunity.
- **D** — Quote history without recent orders.
- **E** — Current-customer/order risk (overdue).
- **F** — New prospect with no BTX internal history (ensure no fabricated
  relationship strength).
- **G** — Irrelevant monitor event (ensure it does not become actionable).
- **H** — Missing/conflicting evidence.
- **I** — Unresolved company/program (graceful handling, no forced incorrect
  resolution).

**New — Scenario J, added by this review**: **Warm-path relationship
discovery.** Given a prospect with no direct BTX history, exercise the full
Phase 2 traversal end-to-end through the UI/Omni: prospect → existing BTX
customer with evidenced affiliation → contact who can open the route → BTX
business-unit owner. This is the actual product thesis behind the
Relationship Intelligence screen (your Figma section 09: *"which existing BTX
customers can credibly open a route into a prospect"*) and deserves an
explicit acceptance scenario, not just Phase 2's backend unit tests. Confirm
the scenario correctly labels each edge as validated (solid path) vs.
needs-validation (dashed path) per the evidence-state model, and that no edge
is inferred from similarity alone.

**Validate every surface**: Today, Accounts, Account Detail, Intelligence,
Map, Actions, Omni.

**Acceptance matrix**: a concise artifact recording scenario, input, expected
behavior, actual behavior, evidence, pass/fail, unresolved defect. Keep it
maintainable, not a QA bureaucracy.

**Verification**: complete backend and frontend test suites. Report all
functional defects found. Fix only defects necessary for POC integrity. Do
not begin final visual styling in this checkpoint.

---

## PHASE 8 — CHOOSE CURRENT FIGMA VERSION AS IMPLEMENTATION BASELINE

No-code checkpoint. When the user says the current Figma version
(`https://www.figma.com/file/QPWPGGDAxEtzG6a69Nsr68`) is ready to implement,
treat that exact state as the next UI implementation baseline. The user
remains free to change Figma later — this checkpoint only prevents Codex from
implementing against a moving target during the visual convergence pass.

---

## PHASE 9 — FIGMA → APPLICATION CONVERGENCE

**Split into four sub-checkpoints by this review** — the original single
prompt bundled polishing six already-implemented screens together with three
entirely new surfaces (Relationship Intelligence, mobile layer, Settings),
which violates the roadmap's own stated principle of checkpoint-sized work.
Do not attempt 9A–9D in one session.

### Prompt 9A — Converge the six existing desktop screens

You are continuing from a functionally validated POC (Phases 0–8 complete).
Do not redesign working backend architecture merely to make implementation
easier; do not change validated domain model, provider model, scoring
semantics, monitor architecture, migration design, relationship architecture,
canonical IDs, or SAMPLE/CONNECTED semantics unless a genuine design/backend
contract conflict is identified and documented.

Implement, screen by screen, against the current Figma file: global shell/nav,
Today (Command Center), Accounts (Account Portfolio), Account Detail (Account
Workspace), Intelligence, Map (shell/controls/panels only — MapLibre itself is
out of scope here, see below), Actions. Match layout, palette, typography,
spacing, hierarchy, information density, cards, tables, filters, controls,
states, and interactions.

**MapLibre**: do not replace real MapLibre with a static Figma representation.
Use Figma to style the map shell, controls, filters, panels, and supporting
UI; preserve actual interactive MapLibre behavior validated in Phase 4.

**Omni**: preserve "always aware, never in the way" — avoid visual treatment
that turns Omni into a dominant generic chat application.

**Functional states**: implement visual states for loading, empty, error,
missing evidence, conflicting evidence, SAMPLE indicators where required,
selected entities, disabled actions.

**Validation**: compare implementation against Figma screen by screen. Run
typecheck, lint, frontend tests, production build, backend tests where
contracts changed, browser console check, responsive checks (desktop
breakpoint only — mobile is Prompt 9C).

**Final report**: screens implemented; intentional deviations; remaining
mismatches; tests; screenshots or run instructions.

### Prompt 9B — Build the Relationship Intelligence screen

Depends on Phase 2 (traversal API) being complete.

**Resolve the graph-explorer tension explicitly before writing UI code**: the
global constraints forbid "a large interactive graph explorer." The Figma
reference screen ("09 — Relationship Intelligence — Operating Model")
describes hover previews, a click-to-pin inspector, and re-centering — but its
own copy also says "keep the graph small by default: strongest validated
paths first; reveal contacts, programs, and overlays only when requested."
Build to that constraint: a bounded, small-by-default list/card view of
validated relationship paths (solid = validated, dashed = needs validation,
per the evidence-state model), with drill-in on request — not a
freely-pannable/zoomable graph canvas. If this doesn't match what the user
actually wants once they see it, that's a Figma iteration to request, not a
scope decision for Codex to make silently.

Implement: default graph (prospect at center → first ring of evidenced
BTX-customer affiliations → contacts/BU owner); separate overlay for
BTX-fulfilled needs/comparable quotes/similar programs (no relationship lines
without real shared-program evidence); evidence & validation labeling on every
path (source, date, confidence, owner); the actions the Figma spec calls for
(open related customer, validate a contact, create an intro task).

**Validation**: exercise Scenario J from Phase 7 through this screen manually.
Run typecheck, lint, frontend tests, production build, backend tests if any
new endpoints were needed beyond Phase 2.

**Final report**: screen implemented; how the graph-explorer tension was
resolved in practice; remaining mismatches vs. Figma; tests.

### Prompt 9C — Build the mobile layer

Production `apps/web/src/design/mobile.css` is currently near-empty (~239
bytes, one topbar breakpoint rule). The Figma file has fully fleshed mobile
mockups for every flow implemented in 9A, plus a consistent bottom tab bar
pattern (Briefing / Intelligence / Accounts / Actions / Omni). This is the
single largest net-new frontend surface in the whole roadmap — size the
checkpoint accordingly and consider splitting further by screen if it runs
long.

Implement mobile layouts for every screen from 9A (not 9B/9D — sequence those
separately once this is stable) matching the Figma mobile mockups: layout
reflow, bottom tab bar, touch target sizing, and the same functional states
(loading/empty/error/evidence states) adapted for the mobile viewport.

**Validation**: responsive checks across the actual breakpoints used in
Figma; manual walkthrough on a real mobile viewport (or device emulation) for
each screen; typecheck, lint, frontend tests, production build.

**Final report**: screens converted; breakpoint strategy; remaining
mismatches; tests.

### Prompt 9D — Build the Settings screen

Exists in Figma ("07 — Settings & Shell") with zero frontend code today.
Lowest-risk of the four 9x checkpoints — implement last.

Implement per Figma: settings shell, whatever configuration surfaces the
Figma file specifies (scoring configuration, source/monitor visibility,
account preferences — confirm exact scope against the current Figma state
per Phase 8's frozen baseline, don't assume). Match desktop and mobile
(depends on 9C).

**Validation**: typecheck, lint, frontend tests, production build.

**Final report**: screen implemented; remaining mismatches; tests.

---

## PHASE 10 — FINAL POC INTEGRITY, DEPLOYMENT, AND SMOKE TEST

### Prompt 10 — Final end-to-end POC acceptance and deployment verification

Do not add major features. Prove the completed application works as one
system.

**Backend verification**: Alembic heads; clean database upgrade; current;
relevant downgrade/re-upgrade checks; sample environment load; provenance
validation; relationship tests; monitor tests; scoring tests; workflow tests;
Omni tests; account API tests; intelligence tests; map API tests; full
backend test suite; Ruff.

**Frontend verification**: typecheck; lint; full frontend tests; production
build. Manually inspect console errors, API failures, loading states, empty
states, responsive behavior, navigation, deep links, refresh behavior.

**Manual application walkthrough** (unchanged from draft): Today — alerts and
priorities appear correctly. Accounts — research accounts load correctly, no
filler/generated companies. Account Detail — public identity and synthetic
commercial context remain distinguishable. Intelligence — recent
source-backed events appear correctly. Map — real MapLibre loads and renders
intended points. Actions — workflow state behaves correctly. Omni —
contextual and free-form behavior works.

**Monitor**: confirm manual invocation still works. Do not enable automatic
scheduling unless explicitly instructed. Document exactly how scheduling
could later be switched on using the same runner.

**Deployment**: only if explicitly part of the current task and
credentials/environment are available. After deployment, verify the actual
hosted system (frontend reachable, backend health, database migration,
SAMPLE data, monitor manual-run capability, Intelligence data, MapLibre
tiles, map points, account navigation, score rendering, Omni, environment
variables, CORS, restart behavior, persistence). Do not treat local success
as proof of deployed success.

**Final POC acceptance report** — sections A–L as originally specified:
repository state; source control; data; monitor; relationship intelligence;
scoring/workflows; MapLibre; Omni; Figma parity; tests; deployment; known
post-POC work (explicitly distinguishing deferred production work from POC
defects).

---

## Deferred until after the POC

Unchanged from the original draft: real Prism/Paperless/HubSpot integration;
broad BTX data-lake access; production security architecture; automatic
monitor scheduling; autonomous system writes; advanced graph visualization;
graph database; deep graph analytics; massive account-universe expansion;
generalized multi-client engine extraction; production capacity modeling;
advanced ML relationship inference; fully autonomous seller agents.

## Intended end state

```
REAL PUBLIC WORLD
        ↓
Monitor / researched evidence
        ↓
Canonical companies, programs, facilities, contacts
        ↓
Relationship intelligence
        ↓
Simulated BTX commercial environment
        ↓
Deterministic scoring / workflows
        ↓
Today / Accounts / Intelligence / Map / Actions
        ↓
Omni
        ↓
Seller understands:
"What happened?"
"Why does it matter to BTX?"
"What evidence supports that?"
"What should I do next?"
```

External-world entities and evidence should be real wherever knowable.
BTX-internal commercial facts remain clearly simulated in SAMPLE mode until
authorized connected access becomes available. The POC should prove that
future real BTX data can replace SAMPLE providers without redesigning the
product.
