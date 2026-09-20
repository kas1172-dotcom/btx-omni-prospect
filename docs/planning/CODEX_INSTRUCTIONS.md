# Codex Instructions — Sample Data Rebuild

**Target:** apply the `docs/research/` replacement and the additive domain expansion cleanly, keeping the codebase clean (no legacy fixtures, no parallel systems, no dead code paths).

---

## Phase 1 — Files to REPLACE (schema-preserving, no code change needed)

These files ship with new content in batch 2. Same schema versions as before. `providers/research/ingestion.py` reads them unchanged.

| Path | Action |
|---|---|
| `docs/research/btx_researched_account_universe.json` | **REPLACE.** Preserve `schema_version: "2.0"`. New content is ~30 BTX-relevant customers. |
| `docs/research/btx_researched_contacts.json` | **REPLACE.** Preserve `schema_version: "2.0"`. New content is named contacts + channels for the new customer set. |
| `docs/research/btx_public_facility_feed_enrichment.json` | **REPLACE.** Preserve `schema_version: "1.0"`. New content is HQ/facilities for new customer set. |
| `docs/research/btx_usaspending_recipient_identities.json` | **REPLACE.** Preserve `schema_version: "1.0"`. New content is recipient mappings for federal-contracting customers in the new set. |
| `docs/research/btx_research_integration_manifest.json` | **REPLACE.** Preserve `schema_version: "1.0"`. Updated to point at the new files and add new integration entries. |

**No changes required in:**
- `providers/research/ingestion.py` — the loader is schema-versioned; it reads the same fields.
- `providers/research/scenarios.py` — the curated RichScenarios still reference `research_account_id` values that will be preserved for the ~10 accounts that appear in both the old and new sets (Boeing, Lockheed Martin, GE Aerospace, Northrop Grumman, SpaceX-style equivalents). See section 3 below for the account-ID transition table.

---

## Phase 2 — Files to ADD (new domain data, requires new loaders)

These files are batch 1 (reference catalogs) and batch 3 (simulated commercial). Codex creates new loader modules for each.

| New file | New loader module | New dataclass usage |
|---|---|---|
| `docs/research/btx_company_profile.json` | `providers/research/btx_profile.py` | New dataclasses: `BtxCompanyProfile`, `BtxBusinessUnit`, `BtxLeadership` (add to `domain/btx.py`) |
| `docs/research/btx_program_catalog.json` | `providers/research/programs.py` | Existing `domain/programs.Program` dataclass (extend fields if needed) |
| `docs/research/btx_component_taxonomy.json` | `providers/research/components.py` | Existing `domain/programs.ComponentClass` dataclass |
| `docs/research/btx_capability_catalog.json` | `providers/research/capabilities.py` | Existing stub `domain/capabilities.Capability` — needs field expansion |
| `docs/research/btx_relationship_edges.json` | `providers/research/relationships.py` | New dataclass `AccountRelationshipEdge` in `domain/relationships.py` |
| `docs/research/btx_sample_paperless_quotes.json` | `providers/paperless_sample/quotes.py` | Existing `domain/quotes.CommercialQuote` |
| `docs/research/btx_sample_orders.json` | `providers/paperless_sample/orders.py` | New dataclass `Order` in `domain/orders.py` (audit section 5 called this out as missing) |
| `docs/research/btx_sample_commercial_context.json` | `providers/lake_sample/context.py` | Existing `domain/commercial.CommercialContext` and `MonthlyCommercialHistory` |
| `docs/research/btx_sample_hubspot_crm.json` | `providers/hubspot_sample/crm.py` | Existing `domain/crm.CrmCompany/CrmContact/CrmDeal/CrmActivity` (populate the richer shapes; current sample uses thin `SampleCrmContext` stand-in) |

Each new loader follows the same pattern as `providers/research/ingestion.py`:
- Validate `schema_version`.
- Reject unknown foreign keys.
- Build the domain dataclass with `Provenance` stamped.
- Return a tuple of records for `PocRuntime.sample` to consume.

---

## Phase 3 — Alembic migration

Add **one new migration** `backend/alembic/versions/0008_commercial_and_edges.py` that creates the tables the console currently keeps only in memory. Reference: audit section 5.

Tables:
- `programs`
- `component_classes`
- `bu_capabilities`
- `btx_facilities` (BTX's own facilities, distinct from the customer `facilities` table)
- `commercial_contexts`
- `monthly_commercial_history`
- `commercial_quotes`
- `paperless_accounts`
- `orders`
- `account_relationship_edges`
- `crm_companies`
- `crm_contacts`
- `crm_deals`
- `crm_activities`

Column shapes: mirror the domain dataclass fields. Foreign keys to `accounts.id` where applicable. Provenance fields (`source_system`, `source_record_id`, `evidence_state`, `data_mode`, `synthetic`) on every table for the SAMPLE/CONNECTED contract.

Add a seed step (or a separate `scripts/seed_sample.py` invoked after `alembic upgrade head`) that loads the new JSON files into the new tables. Recommendation: the seed step lives in `providers/sample/environment.py` as before, but now writes to Postgres instead of only building in-memory tuples.

---

## Phase 4 — Files and code to DELETE

These are legacy or superseded by the replacement. Delete cleanly.

| Path or code | Reason to delete |
|---|---|
| Any hardcoded synthetic BU strings like `"sim-program-lockheed"`, `"SIM-100"`, `"sim-contact-*"`, `"sim-owner-*"`, `"sim-deal-*"`, `"sim-activity-*"`, `"sim-company-*"` in `providers/sample/environment.py` | Replaced by real IDs from the program catalog, real contact IDs from the new contacts file, and CRM records from the new HubSpot sample file. |
| Line 88 `customer_ids = {"boeing", "lockheed-martin", "applied-materials"}` in `providers/sample/environment.py` | The `CURRENT_CUSTOMER` designation now comes from the new account universe's `relationship_state: "BTX_CONFIRMED"` records, not a hardcoded set. |
| `SampleCrmContext` dataclass in `providers/sample/environment.py` | Superseded by populating the real `CrmCompany` / `CrmContact` / `CrmDeal` / `CrmActivity` dataclasses from `btx_sample_hubspot_crm.json`. Remove the thin stand-in. |
| `SamplePublicSignal` dataclass in `providers/sample/environment.py` | Superseded by the RichScenario events (still in `providers/research/scenarios.py`). No parallel signal shape needed. |
| The `SCENARIOS` tuple constant in `providers/sample/environment.py` (line 33) if it duplicates scenarios already in `providers/research/scenarios.py` | Consolidate to one source of truth. Keep the file in `providers/research/scenarios.py`; remove the duplicated tuple in `environment.py`. |

**Do NOT delete:**
- The 12 curated `RichScenario` entries in `providers/research/scenarios.py`. They are the demo signal set. **Codex should update the `research_account_id` values on any scenario whose account is being removed** (see transition table below).
- `SampleHubSpotAdapter` in `integrations/hubspot/contracts.py`. It's the target of the P0.1 bidirectional wiring per the audit. Keep it, extend it.
- `providers/research/ingestion.py`. It works. Reads the schema-preserved files unchanged.

---

## Phase 5 — Account ID transition table

Historical replacement proposal, superseded by additive enhancement: preserve every existing account ID. Current counts are generated in the SAMPLE enhancement report. RichScenarios reference `research_account_id` values and will break if IDs disappear.

Codex mapping actions:
- **Keep the ID as-is** (present in both files, still in RichScenarios): `boeing`, `lockheed-martin`, `northrop-grumman`, `ge-aerospace`, `anduril-industries`, `blue-origin`, `rocket-lab-usa`, `spacex` (add if missing), `intel`, `applied-materials`, `medtronic`, `symbotic`.
- **Remove from RichScenarios** if an ID drops out of the new universe: none in this pass. The RichScenario set overlaps well with the new BTX-relevant universe.
- **Add new IDs** available for future scenarios: `spirit-aerosystems`, `pratt-whitney`, `rtx-collins-aerospace`, `l3harris`, `general-atomics`, `sierra-space`, `ula-united-launch-alliance`, `lam-research`, `kla`, `asml`, `zimmer-biomet`, `stryker`, `boston-scientific`, `intuitive-surgical`, `johnson-johnson-medtech`, `westinghouse`, `terrapower`, `commonwealth-fusion`, `ge-vernova`.

---

## Phase 6 — Sample-provider composition

After phases 1-4, `providers/sample/environment.py` becomes a thin composition module: it reads the JSON files, builds domain objects, and returns a `SampleEnvironment`. No more hardcoded IDs, no more parallel sample shapes.

Recommended new structure:
```
providers/
├── research/          # public research, source of truth for identity
│   ├── ingestion.py   # (existing) loads the 5 schema-preserved files
│   ├── btx_profile.py # NEW: loads btx_company_profile.json
│   ├── programs.py    # NEW: loads btx_program_catalog.json
│   ├── components.py  # NEW: loads btx_component_taxonomy.json
│   ├── capabilities.py # NEW: loads btx_capability_catalog.json
│   └── relationships.py # NEW: loads btx_relationship_edges.json
├── paperless_sample/  # simulated Paperless-shape data
│   ├── quotes.py
│   └── orders.py
├── lake_sample/       # simulated normalized-data-lake shape (Prism source)
│   └── context.py
├── hubspot_sample/    # simulated HubSpot default-property shape
│   └── crm.py
├── sample/
│   └── environment.py # composition: reads all providers, returns SampleEnvironment
└── connected/         # (existing empty) real adapters go here later
```

This structure makes CONNECTED cutover mechanical: swap `paperless_sample/` → `paperless_connected/`, `lake_sample/` → `lake_connected/`, `hubspot_sample/` → `hubspot_connected/`. The `research/` stays because BTX identity research is still needed even in CONNECTED mode.

---

## Phase 7 — Testing

- Every new loader gets a unit test in `backend/tests/` that validates schema version, foreign-key integrity (referenced `research_account_id` values exist), and provenance stamping.
- Integration test that boots `PocRuntime`, walks every account, and asserts that scoring, alerts, matching, and Omni all produce output without errors.
- Test that the account universe's `relationship_state: "BTX_CONFIRMED"` accounts correctly appear as `CURRENT_CUSTOMER` in the API responses.

---

## Phase 8 — Order of operations (recommended)

1. Land new migration `0008_commercial_and_edges.py`.
2. Land new domain files (`domain/orders.py`, `domain/relationships.py`, extend `domain/btx.py`).
3. Land new provider modules (batch 1 loaders first, then batch 3 loaders).
4. Replace `providers/sample/environment.py` composition.
5. Drop the deletions from Phase 4.
6. Refresh the RichScenarios in `providers/research/scenarios.py` per the transition table.
7. Run full test suite, fix breakages.
8. Ship.
