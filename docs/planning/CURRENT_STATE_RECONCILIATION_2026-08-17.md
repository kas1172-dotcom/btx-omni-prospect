# Current-State Reconciliation — 2026-08-17

## Scope and authority

This is a document-organization and current-state reconciliation checkpoint. It does not change product code, migrations, schemas, scoring weights, scoring bins, Figma, integrations, credentials, or deployment state.

Interpretation used here: [WORKFLOW.md](WORKFLOW.md) is the product target; [AUDIT_2026-08-17.md](../audit/AUDIT_2026-08-17.md) is historical; [CODEX_INSTRUCTIONS.md](CODEX_INSTRUCTIONS.md) and the JSON package are the proposed SAMPLE-data specification; current code is authoritative for implementation status. The scoring draft at [BTX_Account_Scoring_Working_Draft (1).docx](../scoring/BTX_Account_Scoring_Working_Draft%20(1).docx) remains unchanged.

The repository already used `docs/research/`, `docs/architecture/`, `docs/product/`, `docs/migration/`, and `docs/deployment/`, but had no audit, planning, or scoring equivalent. `docs/audit/`, `docs/planning/`, and `docs/scoring/` were added as the closest non-redundant locations.

## 1. Already implemented

- A canonical researched-account set is loaded by [backend/src/btx_omni/providers/research/ingestion.py](../../backend/src/btx_omni/providers/research/ingestion.py), converted to `CanonicalAccount`, and enriched with public facilities. It contains only real researched entities; there is no target population or generated filler.
- Monitor 2.0 is implemented: source registry and adapters in [backend/src/btx_omni/monitor/sources.py](../../backend/src/btx_omni/monitor/sources.py), USAspending support in [backend/src/btx_omni/monitor/usaspending.py](../../backend/src/btx_omni/monitor/usaspending.py), service in [backend/src/btx_omni/monitor/service.py](../../backend/src/btx_omni/monitor/service.py), and durable monitor tables in [backend/src/btx_omni/persistence/models.py](../../backend/src/btx_omni/persistence/models.py). Live collection is deliberately fail-closed unless configured.
- Deterministic account-attractiveness scoring is implemented in [backend/src/btx_omni/modules/scoring/account_attractiveness.py](../../backend/src/btx_omni/modules/scoring/account_attractiveness.py), including factor contributions, coverage, missingness, and proportional missing-data handling. Do not change its rubric in this checkpoint.
- The seller-facing surfaces already exist: Today API/UI at [backend/src/btx_omni/api/today.py](../../backend/src/btx_omni/api/today.py) and [apps/web/src/features/today/Today.tsx](../../apps/web/src/features/today/Today.tsx); Account 360 at [backend/src/btx_omni/api/accounts.py](../../backend/src/btx_omni/api/accounts.py) and [apps/web/src/features/accounts/Accounts.tsx](../../apps/web/src/features/accounts/Accounts.tsx); Omni at [backend/src/btx_omni/api/omni.py](../../backend/src/btx_omni/api/omni.py), [backend/src/btx_omni/modules/assistant/orchestration.py](../../backend/src/btx_omni/modules/assistant/orchestration.py), and [apps/web/src/components/OmniDrawer.tsx](../../apps/web/src/components/OmniDrawer.tsx).
- The governed action seam exists in [backend/src/btx_omni/modules/work/service.py](../../backend/src/btx_omni/modules/work/service.py) and [backend/src/btx_omni/api/actions.py](../../backend/src/btx_omni/api/actions.py). CRM execution requires explicit confirmation; the sample adapter remains a stub in [backend/src/btx_omni/integrations/hubspot/contracts.py](../../backend/src/btx_omni/integrations/hubspot/contracts.py).
- SAMPLE versus CONNECTED separation is enforced by [backend/src/btx_omni/api/runtime.py](../../backend/src/btx_omni/api/runtime.py): CONNECTED returns 503 rather than falling back to SAMPLE. Provenance, `evidence_state`, `data_mode`, and synthetic flags are modeled in [backend/src/btx_omni/core/provenance.py](../../backend/src/btx_omni/core/provenance.py).
- The current test suite passes before the data replacement: `uv run pytest tests -q` from `backend/` produced `72 passed`.

## 2. Still missing

- The new program catalog is data-only at [docs/research/btx_program_catalog.json](../research/btx_program_catalog.json); current `Program` and `ComponentClass` shapes in [backend/src/btx_omni/domain/programs.py](../../backend/src/btx_omni/domain/programs.py) are not loaded, persisted, or used for program/component extraction.
- The 30-class taxonomy at [docs/research/btx_component_taxonomy.json](../research/btx_component_taxonomy.json) and the eight-BU catalog at [docs/research/btx_capability_catalog.json](../research/btx_capability_catalog.json) have no loader. `Capability` is still a minimal stub in [backend/src/btx_omni/domain/capabilities.py](../../backend/src/btx_omni/domain/capabilities.py); `api/map.py` still uses one hard-coded BTX Southwest facility.
- The Paperless-shaped quotes ([docs/research/btx_sample_paperless_quotes.json](../research/btx_sample_paperless_quotes.json), 92 quotes) and orders ([docs/research/btx_sample_orders.json](../research/btx_sample_orders.json), 41 orders) are unconsumed. Current [backend/src/btx_omni/domain/quotes.py](../../backend/src/btx_omni/domain/quotes.py) has a thin `PaperlessAccount` and `CommercialQuote`; there is no order domain model.
- Lake-shaped customer × BU × month rows ([docs/research/btx_sample_commercial_context.json](../research/btx_sample_commercial_context.json), 162 rows) and HubSpot-shaped records ([docs/research/btx_sample_hubspot_crm.json](../research/btx_sample_hubspot_crm.json), 31 companies/48 contacts/43 deals/43 activities) are unconsumed. Current CRM uses `SampleCrmContext` in [backend/src/btx_omni/providers/sample/environment.py](../../backend/src/btx_omni/providers/sample/environment.py), not the richer `CrmCompany`, `CrmContact`, `CrmDeal`, and `CrmActivity` types in [backend/src/btx_omni/domain/crm.py](../../backend/src/btx_omni/domain/crm.py).
- There are no persistence tables for programs, components, capabilities, BTX facilities, commercial context/history, Paperless entities, orders, CRM entities, or account relationship edges in [backend/src/btx_omni/persistence/models.py](../../backend/src/btx_omni/persistence/models.py); migrations currently stop at [backend/alembic/versions/0007_usaspending_relevance_state.py](../../backend/alembic/versions/0007_usaspending_relevance_state.py).
- Relationship-edge sample data exists at [docs/research/btx_relationship_edges.json](../research/btx_relationship_edges.json), but there is no relationship domain model, repository, endpoint, or frontend. The relationship-matrix backend/frontend remains missing.
- Action/audit state is still process-memory in [backend/src/btx_omni/modules/work/service.py](../../backend/src/btx_omni/modules/work/service.py), despite tables for work items/audit in [backend/src/btx_omni/persistence/models.py](../../backend/src/btx_omni/persistence/models.py).
- Component extraction is absent. Current normalization in [backend/src/btx_omni/monitor/normalization.py](../../backend/src/btx_omni/monitor/normalization.py) does not consume the taxonomy; Omni is Q&A, not component extraction.

## 3. Superseded by new artifacts

- The previous general, 78-account research content in [docs/research/btx_researched_account_universe.json](../research/btx_researched_account_universe.json), [docs/research/btx_researched_contacts.json](../research/btx_researched_contacts.json), [docs/research/btx_public_facility_feed_enrichment.json](../research/btx_public_facility_feed_enrichment.json), [docs/research/btx_usaspending_recipient_identities.json](../research/btx_usaspending_recipient_identities.json), and [docs/research/btx_research_integration_manifest.json](../research/btx_research_integration_manifest.json) is replaced by the staged BTX-weighted package. The loader-facing schema versions remain `2.0`, `2.0`, `1.0`, `1.0`, and `1.0` respectively.
- Historical audit claims that programs, components, capabilities, orders, CRM population, and relationship edges are wholly absent are superseded as data-availability claims: catalogs/sample datasets now exist at the paths named in section 2. They remain accurate only as implementation-integration claims.
- The historical current-state description of roughly 13 in-memory quotes and no orders in [docs/audit/AUDIT_2026-08-17.md](../audit/AUDIT_2026-08-17.md) is superseded for the intended SAMPLE input; it is still accurate about the current running provider until the next code checkpoint consumes the new 92 quotes and 41 orders.

## 4. Should be deleted or consolidated

Do not delete in this checkpoint.

- [backend/src/btx_omni/providers/sample/environment.py](../../backend/src/btx_omni/providers/sample/environment.py): replace `SCENARIOS`, `SampleCrmContext`, `SamplePublicSignal`, hard-coded `customer_ids`, `sim-*` CRM identifiers, `SIM-100`, `sim-program-lockheed`, the hand-built `CommercialContext` list, hand-built Paperless entities, and the one-record matching fixture only after dedicated loaders compose the staged datasets.
- [backend/src/btx_omni/providers/research/scenarios.py](../../backend/src/btx_omni/providers/research/scenarios.py): retain `RICH_SCENARIOS` as the sole curated public-signal source, but reconcile scenario IDs and static scoring inputs against the BTX-weighted account and program catalog. It currently overlaps neither a generic account generator nor a duplicate signal object; `SamplePublicSignal` is the duplicate shape to remove.
- [backend/src/btx_omni/api/map.py](../../backend/src/btx_omni/api/map.py): replace `BTX_FACILITY` with loaded BTX-facility data when that model exists. Preserve proximity as seller planning input, never an attractiveness factor.
- [backend/src/btx_omni/providers/contracts.py](../../backend/src/btx_omni/providers/contracts.py) and [backend/src/btx_omni/domain/quotes.py](../../backend/src/btx_omni/domain/quotes.py): consolidate the thin quote/provider shape into a Paperless-shaped provider contract rather than retaining parallel quote representations.

## 5. Should be preserved

- `docs/research` ingestion and its schema checks in [backend/src/btx_omni/providers/research/ingestion.py](../../backend/src/btx_omni/providers/research/ingestion.py); the five replacement files have been schema-compared before replacement.
- The 12 curated public scenarios in [backend/src/btx_omni/providers/research/scenarios.py](../../backend/src/btx_omni/providers/research/scenarios.py), subject to the explicit ID gate below.
- Canonical account identity, research/public provenance, missing-data semantics, deterministic scoring, existing migrations, existing tests, and domain boundaries.
- Fail-closed CONNECTED behavior in [backend/src/btx_omni/api/runtime.py](../../backend/src/btx_omni/api/runtime.py), explicit CRM confirmation in [backend/src/btx_omni/api/actions.py](../../backend/src/btx_omni/api/actions.py), and the Monitor 2.0 architecture under [backend/src/btx_omni/monitor/](../../backend/src/btx_omni/monitor/).

## 6. Should be deferred

- Scoring-weight/bins redesign, Signal Confidence redesign, and capacity-fit scoring changes; preserve [BTX_Account_Scoring_Working_Draft (1).docx](../scoring/BTX_Account_Scoring_Working_Draft%20(1).docx) unchanged.
- LLM component extraction; live BTX data-lake, Paperless, and HubSpot integrations; Gemini/provider migration; compliance/deployment migration; relationship-matrix frontend; Figma changes; and mobile redesign.

## 7. Proposed implementation order

1. Resolve the account-ID gate below without inventing aliases: retain `intel`, `symbotic`, and `tsmc-arizona` in the replacement universe or revise the affected curated scenarios with verified replacement IDs and evidence.
2. Add additive domain contracts/loaders for research catalogs, lake SAMPLE, Paperless SAMPLE, and HubSpot SAMPLE. Keep one composition root in `providers/sample/environment.py`; do not create a parallel application system.
3. Add one additive Alembic migration and persistence/repository support for the new SAMPLE shape, retaining provenance fields and all current migration discipline.
4. Recompose runtime/API projections from these providers; replace only the identified hard-coded stand-ins after parity tests.
5. Add relationship backend derivation/read API only after edges are loaded and persisted. Defer its frontend.
6. Re-run and update tests for the verified 31-account input and the workflow path; then consider durable work-action persistence separately.

## 8. Workflow acceptance test

| Workflow stage | Current status and implementation path | Data dependency / current SAMPLE sufficiency | Next checkpoint must add |
|---|---|---|---|
| Public signal | Implemented by `monitor/` and curated `providers/research/scenarios.py`. | Curated public events sufficient; live collection is intentionally gated. | No live source work. Keep public provenance. |
| Canonical account | Implemented by `providers/research/ingestion.py` and `monitor/resolution.py`. | Replacement universe is sufficient after scenario-ID reconciliation. | Resolve `intel`, `symbotic`, `tsmc-arizona` references. |
| Program/components | Program field can appear in curated events; no catalog-backed resolution/extraction. | New catalogs exist but are unconsumed. | Catalog loaders and deterministic catalog lookup; no LLM fallback. |
| BTX addressability | Deterministic quote matching exists in `modules/matching/commercial.py`; capability data is absent from runtime. | New capability/component data sufficient for SAMPLE, but needs loaders. | Load BU capability and component taxonomy; replace hard-coded matching fixture. |
| Quote/order context | Thin in-memory quote context only. | 92 quotes and 41 orders are sufficient as SAMPLE inputs. | Paperless/order loaders, models, persistence, and linkage validation. |
| Commercial/CRM enrichment | In-memory commercial contexts and thin CRM context exist. | 162 monthly rows and HubSpot-shaped CRM data are sufficient. | Lake and CRM loaders plus projections from real domain records. |
| Deterministic score | Implemented in `modules/scoring/account_attractiveness.py`. | Existing scenario inputs work; new data must map without changing weights/bins. | Preserve exact rubric and prove deterministic output/missingness. |
| Seller-facing result | Today, Accounts, Alerts, Omni surfaces implemented. | Current SAMPLE demonstrates the route; richer data is not yet projected. | API projection parity from the clean SAMPLE composition. |
| Human-confirmed action | Implemented in `modules/work/service.py` and `api/actions.py`. | Sufficient for governed SAMPLE demonstration. | No connected write; retain confirmation and audit behavior. |
| Governed CRM/audit seam | Preview/execute seam and audit schema exist; adapter and work state are not durable. | Sufficient only as a stubbed SAMPLE seam. | No live CRM work; optionally defer durable work persistence to a later checkpoint. |

Acceptance: a curated public signal resolves to a canonical account; resolves program/components from catalog; demonstrates capability and historical quote/order evidence; enriches commercial/CRM context; produces the unchanged deterministic score plus provenance/missingness; renders a seller result; and permits only a human-confirmed sample CRM action. CONNECTED must still fail closed.

## 9. Exact next code checkpoint

**Checkpoint:** `0008 clean SAMPLE provider foundation` — make the staged artifacts the one SAMPLE architecture structurally parallel to future CONNECTED providers. Do not add live adapters, UI surfaces, or scoring changes.

Before code begins, resolve the blocking staged-ID mismatch: [backend/src/btx_omni/providers/research/scenarios.py](../../backend/src/btx_omni/providers/research/scenarios.py) references `intel`, `symbotic`, and `tsmc-arizona`, which are absent from [docs/research/btx_researched_account_universe.json](../research/btx_researched_account_universe.json). The instructions’ stated transition table is therefore not verified by the delivered artifact.

Files to modify:

- [backend/src/btx_omni/providers/sample/environment.py](../../backend/src/btx_omni/providers/sample/environment.py), [backend/src/btx_omni/api/runtime.py](../../backend/src/btx_omni/api/runtime.py), [backend/src/btx_omni/api/accounts.py](../../backend/src/btx_omni/api/accounts.py), [backend/src/btx_omni/api/map.py](../../backend/src/btx_omni/api/map.py), [backend/src/btx_omni/domain/programs.py](../../backend/src/btx_omni/domain/programs.py), [backend/src/btx_omni/domain/capabilities.py](../../backend/src/btx_omni/domain/capabilities.py), [backend/src/btx_omni/domain/quotes.py](../../backend/src/btx_omni/domain/quotes.py), [backend/src/btx_omni/domain/crm.py](../../backend/src/btx_omni/domain/crm.py), [backend/src/btx_omni/persistence/models.py](../../backend/src/btx_omni/persistence/models.py), and [backend/src/btx_omni/providers/contracts.py](../../backend/src/btx_omni/providers/contracts.py).

Files to add:

- `backend/alembic/versions/0008_commercial_and_edges.py`; `backend/src/btx_omni/domain/btx.py`, `domain/orders.py`, and `domain/relationships.py`; `backend/src/btx_omni/providers/research/{btx_profile,programs,components,capabilities,relationships}.py`; `backend/src/btx_omni/providers/{lake_sample,paperless_sample,hubspot_sample}/` loaders; and focused loader/integration tests under `backend/tests/`.

Later-delete candidates after parity tests: `SampleCrmContext`, `SamplePublicSignal`, the local `SCENARIOS`, `customer_ids`, `SIM-100`, `sim-program-lockheed`, the `sim-*` identifiers, manually constructed quote/context collections, and `BTX_FACILITY` at the exact paths cited in section 4.

Migration required: one additive `0008_commercial_and_edges.py` for programs, component classes, BU capabilities, BTX facilities, commercial contexts/monthly history, Paperless accounts/quotes/items, orders, account relationship edges, and CRM records. Include provenance/evidence/data-mode/synthetic fields; do not alter existing migrations.

Tests required: schema-version and foreign-key validation for every loader; explicit scenario-ID integrity; provenance/SAMPLE assertions; loader-to-runtime integration across all accounts; unchanged scoring determinism/missingness; alerts/matching/Omni smoke coverage; connected-mode 503; and human-confirmed CRM-write seam tests.

Explicit non-goals: scoring redesign; LLM extraction; live Prism/Paperless/HubSpot; Gemini migration; relationship frontend; Figma/mobile; deployment/compliance work; or deletion before parity.
