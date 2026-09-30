# Public Intelligence Monitor Functional Certification

Date: 2026-09-30  
Branch: `codex/monitor-functional-certification`  
Base: `df4eccb`  
Status: **PARTIALLY CERTIFIED — production-like Gemini-assisted publication is not verified in this environment.**

This report separates executed evidence from source inspection. No production
endpoint, secret, Fly resource, or live customer data was used.

## Architecture flow

| Module/file | Responsibility | Input | Output |
|---|---|---|---|
| `monitor/sources.py` | Governed provider adapters, bounded retrieval, parsing, source identity, content hash, timestamps | Provider response | `SourceObservation` + `RawEvidenceReference` |
| `monitor/service.py` | Collection orchestration, cursor/health state, normalization, clustering, durable writes | Source adapter observations | `IntelligenceEvent`, collection run, source health, candidates |
| `monitor/normalization.py` | Deterministic event type, claims, market, freshness, provenance and resolution projection | `SourceObservation` + catalog | `IntelligenceEvent` |
| `monitor/catalog.py`, `monitor/resolution.py`, `monitor/entity_candidates.py` | Canonical account/program/facility matching and bounded review candidates | Source text, identifiers, watch profiles | Resolved, unresolved, or ambiguous identity; review candidates |
| `monitor/documents.py`, `monitor/research.py` | Evidence retention and bounded public research journal | Source document + allowed public tool choices | Evidence passages, research run/steps, source revisions |
| `monitor/briefs.py`, `monitor/business_briefings.py` | Seller Signal Brief projection, deterministic evidence package, synthesis cache, assessment persistence | Event, evidence, research, environment | Brief, assessment, deterministic gates |
| `ai/*`, `modules/intelligence/technical_fit.py` | Optional Gemini-assisted research/tool choice, technical decomposition, seller-language synthesis | Public evidence and bounded structured requests | Cached prose/decomposition; never canonical truth or gate authority |
| `monitor/worker.py` | Bounded operational sequence and publication gate evaluation | Collection runs and durable projections | Research, decomposition, synthesis, publication outcomes |
| `monitor/repository.py` and `persistence/models.py` | Durable idempotent rows and read projections | Canonical monitor objects | Runs, observations, versions, events, contexts, assessments, briefs, decompositions |
| `api/monitor.py`, `api/intelligence.py`, `api/accounts.py`, `api/today.py`, `api/omni.py`, `api/map.py` | Seller/admin dispensing | Durable projections and current environment | Monitor health, Intelligence, Customer 360, Today, Omni, Map payloads |
| `apps/web/src/features/intelligence/Intelligence.tsx`, `today/Today.tsx`, account/Map/Omni components | Progressive seller presentation | API payloads | Feed, account intelligence, priority cards, context-aware Omni |

Pipeline: `provider -> observation/evidence -> deterministic normalization and
matching -> retained document/research -> technical projection -> deterministic
assessment -> optional Gemini synthesis -> deterministic publication gates ->
durable assessment/brief -> Intelligence/Customer 360/Today/Map/Omni`.

### Gemini boundary

Gemini is used, when configured, for bounded public research tool selection,
public research synthesis/selection, technical decomposition assistance,
governed explanations, and seller-language brief synthesis. It is not the
authority for canonical account identity, deterministic scores, publication
thresholds, permissions, or source truth. The worker evaluates publication
gates itself (`research_completed`, canonical identity, seller relevance,
analysis readiness, commercial relevance, technical availability, and brief
availability).

## Provider/source status

| Source | Mode/status in this certification | Endpoint/notes |
|---|---|---|
| `federal_register` | **LIVE verified** | `https://www.federalregister.gov/api/v1/documents.json`; one connected observation/event persisted |
| `nasa` | **LIVE verified** | NASA RSS; one connected observation/event persisted |
| `fda_openfda` | **LIVE verified** | `https://api.fda.gov/device/510k.json`; one connected observation/event persisted |
| `dod` | **LIVE verified** | Official DoD RSS; one connected observation/event persisted |
| `sam_gov` | **NOT CONFIGURED** | Requires `SAM_API_KEY` |
| `usaspending` | **NOT CONFIGURED** | Keyless endpoint, but no targeted returned record was used for a golden customer case in this run |
| `sec_edgar` | **NOT CONFIGURED** | Requires configured SEC targets/CIK coverage in the runtime |
| `commerce` | **NOT CONFIGURED** | Requires `BTX_COMMERCE_API_KEY` |
| `company_newsroom` | **CONFIGURATION-DEPENDENT** | Only explicitly governed owner feeds are permitted; default registry was not treated as a verified seller source |
| `state_economic_development` | **NOT CONFIGURED** | Requires governed official publisher registry |

The live probe used bounded limit 1 and no production secrets. It recorded
source URL, source ID, publication/collection metadata and content hashes. The
returned records did not contain seeded BTX identities, so they correctly
remained unresolved rather than being forced into a customer.

## Golden cases

| Case | Executed evidence | Result |
|---|---|---|
| Existing customer + defense procurement | Deterministic adapter, catalog, normalization, technical-fit, brief and publication-gate tests; Lockheed/Boeing source-shaped fixtures | **PARTIAL**: fixture/unit path verified; no credentialed live defense award plus configured Gemini run executed |
| New prospect | Candidate/resolution/promotion governance tests, including non-collision requirements | **PARTIAL**: unresolved candidate safety verified; explicit connected promotion requires governed provenance and confirmation |
| Existing customer expansion | Expansion/risk/brief fixtures and monitor business-briefing tests | **PARTIAL**: deterministic retained-account behavior verified; no live end-to-end publication run |
| Low-quality/non-durable signal | stale, unresolved, missing-date and insufficient-evidence tests | **GO for deterministic withholding** |
| Ambiguous entity match | alias collision and conflicting identifier tests | **GO**: ambiguous/unknown identities do not become promotion-ready |
| Duplicate/repeated source | clustering, source-version and research-journal idempotency tests | **GO for tested boundaries**; no duplicate current event/assessment is created for unchanged versions |

## Matching and decomposition

Canonical matching is deterministic and uses watch-profile names, aliases,
source-native identifiers, domains, facilities and catalog rules. Tests verify
that authoritative identifiers win, collisions become `AMBIGUOUS`, and unknown
names remain unresolved. Gemini is not required to approve a canonical account.

Technical decomposition is retained as a separate projection with evidence IDs,
source revision, provider/model/status and controlled matches. The seller
projection distinguishes source-backed facts from hypotheses and unavailable
information; unsupported components are not promoted to facts. The existing
Lockheed/Boeing technical-fit and business-briefing tests verify this boundary,
but a configured Gemini production-like decomposition was not executed here.

## Deterministic scoring and publication

Public signal scoring is defined in `modules/scoring/public_inputs.py` and
`monitor/policy.py`; opportunity qualification is separately defined in
`modules/scoring/opportunity_gates.py`. Account attractiveness, internal risk,
prospect fit, action priority and public signal confidence are distinct score
families and are not averaged together.

The executable tests verify:

- identical structured inputs produce identical score/band/disposition;
- missing evidence produces `INSUFFICIENT_EVIDENCE`, not a fabricated score;
- freshness, resolution, seller relevance and technical readiness are separate;
- low-quality, stale, unresolved or unresearched items cannot become a durable
  published seller brief merely because prose is available;
- Gemini synthesis is cached by governed content hash and does not alter the
  deterministic score or gate inputs.

Publication is withheld unless the worker’s explicit gates all pass. The
low-quality, stale, ambiguous and unresolved cases therefore have a verified
deterministic withholding path. Full Gemini-assisted publication is **not yet
verified** because the required provider credentials are unavailable.

## Persistence and idempotency

The repository persists collection runs, source observations, source versions
and hashes, events/clusters, organization/program candidates, research runs and
steps, technical decompositions, brief syntheses, intelligence assessments and
publication outcomes. Repeated source identities are versioned by content hash;
research publication outcomes are idempotently recorded; current assessments
are selected by canonical event/account context.

Executed tests cover unchanged-source dedupe, changed-source replacement,
partial collection failure retention, journal lease/publication idempotency,
technical cache reuse and deterministic assessment persistence. A complete
live six-case replay against PostgreSQL with Gemini was not possible without
provider credentials and a configured live defense target.

## Omni surface dispensing

Source inspection and frontend unit contracts verify the intended dispensing
paths:

- Intelligence consumes governed current/research Signal Briefs;
- Customer/Prospect 360 scopes briefs by canonical account;
- Today consumes priority/current curated projections;
- Map uses the same canonical site/intelligence arrays where geographic data is
  available;
- Actions can use assessment context without inventing account identity;
- Omni receives the selected canonical event/assessment context and clears stale
  passive context on navigation.

The integrated branch’s CI-certified browser suite passed 210/210 Chromium and
92/92 WebKit compatibility tests. Those tests validate seller dispensing and
Omni context contracts, but they do not constitute a live Gemini publication
run for a newly collected external defense event.

## Executed validation

- Core Monitor/live/operations/research/briefing group: **117 passed, 5 skipped**.
- Funnel/identity/date/discovery/federal/deadline group: **54 passed, 5 skipped**.
- Live keyless probe: Federal Register, NASA, FDA and DoD: **4/4 bounded
  collections succeeded**, connected provenance recorded; all four returned
  unresolved identities as expected for the sampled records.
- Frontend: typecheck, lint, 130 unit tests, build: **passed**.
- Browser baseline on the certified parent SHA: Chromium **210/210**, WebKit
  compatibility **92/92**.
- Migration used by the integrated branch: `0043_query_support_indexes`.

## Known limitations and production-only checks

The following remain **NOT YET VERIFIED**, not failed:

1. Credentialed SAM.gov/Commerce and configured SEC target collection.
2. A live defense award that resolves to a seeded BTX customer and completes
   research, technical decomposition, Gemini synthesis and publication.
3. Gemini timeout/fallback behavior during a full newly collected event replay.
4. Production scheduler/worker environment, credentials, rate limits and live
   source freshness under Fly.
5. End-to-end seller verification of a newly published live item across every
   surface listed above.

These require credentials or production-like external access and are outside
this safe local certification phase. No production or Fly change was made.

## Certification decision

| Stage | Status |
|---|---|
| Source adapters, parsing, provenance, timestamps, hashes | **GO for tested live/keyless and fixture paths** |
| Deterministic normalization, matching, ambiguity handling | **GO** |
| Evidence retention and bounded research journal | **GO for tested paths** |
| Deterministic scoring and publication gates | **GO** |
| Low-quality/ambiguous/deduplicated safety behavior | **GO** |
| Full live defense golden path with Gemini | **NOT YET VERIFIED** |
| Production credentialed providers and scheduler | **NOT YET VERIFIED** |
| Newly published live item across all seller surfaces | **NOT YET VERIFIED** |

Overall: **PARTIALLY CERTIFIED — exact blocking stages are the credentialed
live/Gemini end-to-end path and production-only source/scheduler verification.**
