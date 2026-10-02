# Data baseline — source-only partial snapshot

Scope: checked-out Python source, not a connected PostgreSQL database. The Codex tool environment cannot reach the host's PostgreSQL instance; per instruction, no further database connection was attempted. The 95 tables below are **SQLAlchemy shared-metadata declarations**, not verified database tables. No schema, model, migration, application, or test file was changed.

## Section 1 — Schema inventory (verified against the database)

**PENDING DATABASE ACCESS.** No live table, column, constraint, or model-drift claim is made here.

## Section 2 — Index inventory

**PENDING DATABASE ACCESS.** Index definitions and `pg_stat_user_indexes` usage require the database.

## Section 3 — Foreign key graph

**PENDING DATABASE ACCESS.** The declared FKs alone cannot establish the database FK graph or orphan state.

## Section 4 — Query pattern map

**PENDING DATABASE ACCESS.** SQL source can be inspected separately, but index coverage cannot be verified without the database catalog.

## Section 5 — In-memory data structures inventory

The narrowed AST scan covered 240 Python files under `backend/src/btx_omni/`. It counted **38** module-level dictionary assignments, **0** class-level dictionary attributes in known module-level/singleton classes, **6** cache-decorated functions, **10** repository result-to-dictionary materializations, and **8** dictionary lookup structures rebuilt inside nontrivially bounded/runtime-sized loops (**62** items total). Counts are per assignment/construction site, not live instances. No category exceeds 100. The search was restricted to module/class assignment nodes with dict literal/comprehension or `dict`/`defaultdict` constructor, decorators named `lru_cache`/`cache`/`cached_property`, and manually reviewed method/loop candidates that consume a `connection.execute(select(...))` result. Ordinary row-projection dicts and bounded loops (for example the technical worker cap of at most five) were excluded.

### (a) Module-level dictionaries — 38

Each is built at module import and survives for the process lifetime. Static literals are bounded by their source definitions; catalog-derived comprehensions are bounded by their loaded catalog. No automatic invalidation or refresh is visible: re-import/process restart is the effective refresh. The key/value sample is from each AST assignment; “same-module probes” lists direct name-load line numbers (cross-module imports are not exhaustively traced). Under the requested classification vocabulary these are **CACHE**/process-lifetime lookups, though most are static policy or catalog maps rather than eviction caches.

| Build site | Variable | Key → value example | Same-module probes |
| --- | --- | --- | --- |
| [`domain/markets.py:21`](../../backend/src/btx_omni/domain/markets.py#L21) | `_SOURCE_ALIASES` | `'commercial aerospace' → CanonicalMarket.COMMERCIAL_AEROSPAC` | 48 |
| [`modules/assistant/chat_tools.py:69`](../../backend/src/btx_omni/modules/assistant/chat_tools.py#L69) | `INPUTS` | `'web_search' → (Search, 'Search public sources usi` | 131, 157, 159 |
| [`modules/assistant/chat_validation.py:5`](../../backend/src/btx_omni/modules/assistant/chat_validation.py#L5) | `GENERAL_FACTS` | `'capital of france' → 'Paris is the capital of France.'` | none in module |
| [`modules/assistant/orchestration.py:22`](../../backend/src/btx_omni/modules/assistant/orchestration.py#L22) | `_ALERT_LABELS` | `'CUSTOMER_INACTIVITY' → 'No recent customer activity'` | 371 |
| [`modules/commercial/ledger.py:17`](../../backend/src/btx_omni/modules/commercial/ledger.py#L17) | `KEYS` | `'programs' → 'program_id'` | 49 |
| [`modules/federal_procurement.py:31`](../../backend/src/btx_omni/modules/federal_procurement.py#L31) | `NOTICE` | `'SOLICITATION' → 'Solicitation'` | 67, 603 |
| [`modules/intelligence/technical_fit.py:38`](../../backend/src/btx_omni/modules/intelligence/technical_fit.py#L38) | `APPROVED_ALIASES` | `'cc-actuator' → ('actuator housing', 'actuator hous` | 340 |
| [`modules/intelligence/technical_fit.py:50`](../../backend/src/btx_omni/modules/intelligence/technical_fit.py#L50) | `CATEGORY_COMPONENTS` | `'GUIDANCE_ELECTRONICS' → ('cc-sensor-housing',)` | 342 |
| [`modules/markets/registry.py:47`](../../backend/src/btx_omni/modules/markets/registry.py#L47) | `BY_ID` | `series.id → series` | none in module |
| [`modules/markets/registry.py:48`](../../backend/src/btx_omni/modules/markets/registry.py#L48) | `BY_CODE` | `series.native_code → series` | none in module |
| [`modules/priority_ordering.py:38`](../../backend/src/btx_omni/modules/priority_ordering.py#L38) | `INTERNAL_NATURE` | `'CUSTOMER_INACTIVITY' → 'RISK'` | 195 |
| [`modules/priority_ordering.py:48`](../../backend/src/btx_omni/modules/priority_ordering.py#L48) | `PUBLIC_NATURE` | `dict unpack/empty` | 183 |
| [`modules/priority_ordering.py:106`](../../backend/src/btx_omni/modules/priority_ordering.py#L106) | `TIER_RANK` | `'CRITICAL' → 100` | 336 |
| [`modules/relationships/canonical_projection.py:21`](../../backend/src/btx_omni/modules/relationships/canonical_projection.py#L21) | `FACILITY_CROSSWALK` | `'BTX-FAC-BU-ERA' → 'era-elk-grove'` | 57, 58, 105 |
| [`modules/relationships/presentation.py:9`](../../backend/src/btx_omni/modules/relationships/presentation.py#L9) | `RELATIONSHIP_POLICY` | `'PARENT_CHILD' → ('Organizational relationship', 'Th` | 50 |
| [`modules/relationships/record_projection.py:13`](../../backend/src/btx_omni/modules/relationships/record_projection.py#L13) | `FIELDS` | `'rfqs' → ('program_id', 'component_ids', 're` | 37, 55 |
| [`modules/relationships/record_projection.py:33`](../../backend/src/btx_omni/modules/relationships/record_projection.py#L33) | `DATES` | `'rfqs' → 'received_date'` | 49 |
| [`modules/relationships/routes.py:22`](../../backend/src/btx_omni/modules/relationships/routes.py#L22) | `TEMPLATES` | `'cross_account_experienc → (('SCENARIO_SUPPLIER_FOR_COMPONENT:` | 197 |
| [`modules/scoring/families.py:27`](../../backend/src/btx_omni/modules/scoring/families.py#L27) | `FAMILIES` | `f.key → f` | 81 |
| [`modules/scoring/public_rules.py:5`](../../backend/src/btx_omni/modules/scoring/public_rules.py#L5) | `SOURCE_POINTS` | `'TIER_1_AUTHORITATIVE_ST → 100` | none in module |
| [`modules/scoring/public_rules.py:74`](../../backend/src/btx_omni/modules/scoring/public_rules.py#L74) | `RISK_FIELDS` | `'impact' → ('risk_condition', 'program_reducti` | none in module |
| [`modules/scoring/pursuit_inputs.py:12`](../../backend/src/btx_omni/modules/scoring/pursuit_inputs.py#L12) | `_BINS` | `'buyer_access' → {'DECISION_AUTHORITY_TWO_WAY': 100,` | 36, 37 |
| [`monitor/briefs.py:38`](../../backend/src/btx_omni/monitor/briefs.py#L38) | `EVENT_LABELS` | `'CONTRACT_AWARD' → 'Contract award reported'` | 212 |
| [`monitor/packs/__init__.py:4`](../../backend/src/btx_omni/monitor/packs/__init__.py#L4) | `PACKS` | `'commercial_aerospace' → IndustryPack('commercial_aerospace'` | none in module |
| [`monitor/policy.py:14`](../../backend/src/btx_omni/monitor/policy.py#L14) | `MARKET_KEYWORDS` | `'Commercial Aerospace' → ('commercial aircraft', 'civil avia` | 60 |
| [`monitor/research.py:27`](../../backend/src/btx_omni/monitor/research.py#L27) | `FOCUSES` | `'program' → 'official program product and opera` | 97, 116, 135 |
| [`monitor/sources.py:1538`](../../backend/src/btx_omni/monitor/sources.py#L1538) | `REGISTRY` | `adapter.definition.sourc → adapter` | none in module |
| [`persistence/commercial_import.py:32`](../../backend/src/btx_omni/persistence/commercial_import.py#L32) | `BU_CROSSWALK` | `'BU-ERA' → 'era-industries'` | 80, 210, 214, 219 (+1) |
| [`persistence/commercial_schema.py:36`](../../backend/src/btx_omni/persistence/commercial_schema.py#L36) | `LIFECYCLE_TABLES` | `name → _records('commercial_' + name)` | 46 |
| [`persistence/commercial_schema.py:45`](../../backend/src/btx_omni/persistence/commercial_schema.py#L45) | `COLLECTION_TABLES` | `'programs' → programs` | none in module |
| [`persistence/import_commercial_sample.py:19`](../../backend/src/btx_omni/persistence/import_commercial_sample.py#L19) | `ACCOUNT_CROSSWALK` | `'ACC-HONEYWELL' → 'honeywell'` | 33, 57 |
| [`providers/paperless_sample/quotes.py:14`](../../backend/src/btx_omni/providers/paperless_sample/quotes.py#L14) | `_STATUS` | `'OUTSTANDING' → QuoteStatus.OPEN` | 25, 35 |
| [`providers/research/scenarios.py:54`](../../backend/src/btx_omni/providers/research/scenarios.py#L54) | `STRONG` | `'program_durability.expe → 'FIVE_TO_NINE_YEARS'` | 62, 64, 66, 69 |
| [`providers/research/scenarios.py:55`](../../backend/src/btx_omni/providers/research/scenarios.py#L55) | `WARM_DECLINING` | `'program_durability.expe → 'TWO_TO_FOUR_YEARS'` | 70 |
| [`providers/research/scenarios.py:56`](../../backend/src/btx_omni/providers/research/scenarios.py#L56) | `POOR_FIT` | `'btx_manufacturing_fit.c → 'MAJOR_GAP'` | 65 |
| [`providers/research/scenarios.py:57`](../../backend/src/btx_omni/providers/research/scenarios.py#L57) | `LOW_EVIDENCE` | `'strategic_target_fit' → 'STRONG_TARGET_ARCHETYPE'` | 67, 71 |
| [`providers/sample/medical_market.py:18`](../../backend/src/btx_omni/providers/sample/medical_market.py#L18) | `VALUES` | `2024 → '101.3492 102.6200 101.2494 100.269` | 30 |
| [`providers/sample/scoring_cases.py:12`](../../backend/src/btx_omni/providers/sample/scoring_cases.py#L12) | `EXPANSION_BINS` | `'program_durability.expe → 'FIVE_TO_NINE_YEARS'` | 120 |

### (b) Class-level dictionaries in singleton/module-level instances — 0

The raw class-body scan found only three `model_config` dictionaries on request models in `api/communications.py:39,47,53`. Those classes are not module-level singleton instances, so none qualifies for this category.

### (c) Cache-decorated functions — 6

| Build site | Cached key → value; lifetime/bound | Invalidation and classification |
| --- | --- | --- |
| `core/config.py:150` `get_settings` | no arguments → `Settings`; process-lifetime, one effective key | No `cache_clear` call found; **CACHE**. |
| `persistence/database.py:50` `get_engine` | no arguments → SQLAlchemy engine; process-lifetime, one effective key | No explicit invalidation found; **CACHE**. |
| `persistence/database.py:57` `get_session_factory` | no arguments → session factory; process-lifetime, one effective key | No explicit invalidation found; **CACHE**. |
| `ai/config.py:9` `usage_repository` | database URL → repository; process-lifetime, `maxsize=8` | LRU eviction beyond eight keys; **CACHE**. |
| `modules/relationships/canonical_projection.py:25` `relationship_catalog` | no arguments → catalog dict; process-lifetime, `maxsize=1` | No explicit invalidation found; **CACHE**. |
| `providers/research/enriched_evidence.py:7` `public_sources` | no arguments → source-ID-to-source dict; process-lifetime, `maxsize=1` | No explicit invalidation found; **CACHE**. |

These are populated on first call and probed by later calls to the decorated function. Bare `@lru_cache` has a default maximum of 128, but the no-argument functions have only one effective cache key.

### (d) Repository SQL-result dictionaries — 10

These are function/request-lifetime dictionaries. “Full” describes the SQL scope, not necessarily the whole physical table. A bounded request-key lookup is **CORRECT_USE**; a full-scope lookup is a **SHOULD_BE_A_QUERY review candidate** only when its caller does not require the full map. No query rewrite is proposed here.

| Build site | Key → value; build/probe | SQL scope; classification |
| --- | --- | --- |
| `monitor/repository.py:1336` `candidates.promotions` | candidate ID → audit row; probed while mapping organization page | Returned candidate IDs only; **CORRECT_USE**. |
| `monitor/repository.py:1344` `candidates.program_promotions` | candidate ID → audit row; probed while mapping program page | Returned candidate IDs only; **CORRECT_USE**. |
| `monitor/repository.py:1393` `source_content_hashes` | (source ID, record ID) → hash; caller probes requested pairs | Requested-pair `IN`; **CORRECT_USE**. |
| `monitor/repository.py:1435` `brief_syntheses` | (brief ID, governed hash) → decoded row; caller probes requested pairs | Requested-pair `IN`; **CORRECT_USE**. |
| `monitor/repository.py:2056` `latest_governed_explanations` | subject key → decoded row; caller probes requested keys | Requested-key `IN`; **CORRECT_USE**. |
| `monitor/research_state.py:251` `latest_statuses_for_sources` | (event reference, revision) → status; caller probes requested pairs | Window-ranked requested pairs; **CORRECT_USE**. |
| `persistence/commercial_import.py:245` `_crm_mappings` | account ID → CRM mapping; probed by commercial projection | All rows for the sample package; **SHOULD_BE_A_QUERY review candidate** if consumers need only selected accounts. |
| `persistence/commercial_import.py:288` `snapshot.result` | account ID → decoded profile; probed while assembling collections | All package profiles by snapshot contract; **CORRECT_USE** for that contract. |
| `persistence/work_feedback.py:106` `current.result` | suggestion ID → latest feedback; probed by caller | Requested suggestions capped at 500; **CORRECT_USE**. |
| `persistence/reference_fields.py:103` `import_package.prior` | row key → current version ID; probed for revision/omission checks | All current reference rows; **SHOULD_BE_A_QUERY review candidate** if a bounded comparison can preserve the revision contract. |

### (e) Rebuilt lookup dictionaries inside loops — 8

The loop itself is runtime-sized or may exceed a small fixed count; each mapping is local to one iteration and then discarded. These are **ANTI_PATTERN review flags** under the requested structural definition, not measured performance defects. Row-shaped dicts appended to output were excluded.

| Build site | Key → value; build/probe | Outer loop / lifetime |
| --- | --- | --- |
| `persistence/commercial_import.py:182` `components` | component ID → component; probes quote-line/component mapping | One map per imported account. |
| `persistence/commercial_import.py:183` `revisions` | revision ID → revision; probes current quote revision | One map per imported account. |
| `persistence/commercial_import.py:184` `quote_lines` | quote-line ID → line; probes quote components | One map per imported account. |
| `persistence/commercial_import.py:185` `order_lines` | order-line ID → line; probes order fields | One map per imported account. |
| `persistence/commercial_import.py:307` `by_id` | record key → decoded record; probes source order | Rebuilt per account and collection during snapshot reconstruction. |
| `persistence/reference_fields.py:80` `columns` | column label → source cell/header; probes validated fields | Rebuilt per workbook row; import permits up to 2,000 rows. |
| `modules/relationships/canonical_projection.py:75` `constraints_by_component` | component ID → constraint IDs; probes component experience | Rebuilt per commercial ledger/account. |
| `modules/relationships/canonical_projection.py:88` `lines` | order-line ID → line; probes accepted-work joins | Rebuilt per commercial ledger/account. |

Required non-category callouts: `monitor/repository.py:84` `_replace_rows.unique_rows` maps key-column tuple → last input row once per write operation (**CORRECT_USE**, function-scope); `monitor/repository.py:616` `observation_by_evidence` maps evidence ID → first observation position/record before the event loop (**CORRECT_USE**, function-scope). Neither is a full-query materialization nor a dict rebuilt inside the event loop. The one-program catalog in `docs/research/technical_program_reference_sources.json` makes `providers/research/technical_programs.py:35` `source_by_id` a small bounded per-program construction, excluded from (e).

### Resolution — reviewed 2026-09-29

All eight loop-rebuilt maps and all six cache-decorated functions have
been reviewed against their callers and are correct as written.

- commercial_import.py:307 by_id is bounded to the current collection's
  profile list; the map's key space changes per collection, so it cannot
  be hoisted.
- canonical_projection.py:75 and :88 maps depend on the current account
  and its freshly computed fulfillment state; project_route_graph is
  called once per ranked_routes call, with no caller-side loop.
- config.get_settings, database.get_engine, database.get_session_factory,
  and ai.config.usage_repository are singleton caches of immutable
  process-level objects.
- canonical_projection.relationship_catalog and
  providers/research.enriched_evidence.public_sources cache static
  tracked files with no runtime writer; they will be revisited at
  Milestone B if the source becomes dynamic.

No action required for Milestone A.

## Section 6 — Data type decisions

This is a **declaration-level type-change inventory**, not a claim about live PostgreSQL values or an approved migration. It covers shared metadata declared by `persistence/models.py`, `commercial_schema.py`, `monitor/research_state.py`, and the other persistence table-declarer modules. **98 columns** meet the source-level categories: 9 date/month strings, 4 coordinate strings, and 85 structured-JSON Text columns. Conversion of every existing value and all readers/writers would have to be verified separately. “B (integration)” records the requested pre-Milestone-B target, not a migration authorization. JSONB changes are coordinated code changes because many readers call `json.loads` and writers serialize with `json.dumps`/`encoded`/`_json`; date columns likewise have string API contracts.

### DATE_STORED_AS_STRING (9)

| Column | Declared type | Target type | Reason | Complexity | Milestone |
| --- | --- | --- | --- | --- | --- |
| `action_subtasks.due_date` | `VARCHAR(16)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_import_runs.as_of` | `VARCHAR(10)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_quotes.quoted_at` | `VARCHAR(10)` | `DATE` | ISO quote date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `market_series_vintages.release_date` | `VARCHAR(10)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monthly_commercial_history.month` | `VARCHAR(10)` | `DATE` (month: first-of-month convention) | month period encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `orders.promised_date` | `VARCHAR(10)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `orders.actual_ship_date` | `VARCHAR(10)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `seller_shortlist_items.target_date` | `VARCHAR(10)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `work_items.due_date` | `VARCHAR(16)` | `DATE` | ISO date encoded as string | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |

### COORDINATE_STORED_AS_STRING (4)

| Column | Declared type | Target type | Reason | Complexity | Milestone |
| --- | --- | --- | --- | --- | --- |
| `btx_facilities.latitude` | `VARCHAR(32)` | `NUMERIC(9,6)` | Coordinates need numeric validation/range semantics | NEEDS_PARSE_STEP | B (integration) |
| `btx_facilities.longitude` | `VARCHAR(32)` | `NUMERIC(9,6)` | Coordinates need numeric validation/range semantics | NEEDS_PARSE_STEP | B (integration) |
| `facilities.latitude` | `VARCHAR(32)` | `NUMERIC(9,6)` | Coordinates need numeric validation/range semantics | NEEDS_PARSE_STEP | B (integration) |
| `facilities.longitude` | `VARCHAR(32)` | `NUMERIC(9,6)` | Coordinates need numeric validation/range semantics | NEEDS_PARSE_STEP | B (integration) |

### JSON_STORED_AS_TEXT (85)

| Column | Declared type | Target type | Reason | Complexity | Milestone |
| --- | --- | --- | --- | --- | --- |
| `account_relationship_edges.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `ai_call_receipts.policy` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `ai_call_receipts.usage` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `assistant_turns.citation_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `bu_capabilities.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_acceptances.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_account_profiles.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_actions.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_agreements.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_alerts.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_cancellations.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_contacts.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_contexts.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_fulfillment_plans.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_import_runs.report` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_invoices.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_matches.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_order_lines.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_payments.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_quote_lines.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_quote_revisions.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_quotes.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_revenue_events.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_rfqs.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_role_targets.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_service_events.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_shipments.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `commercial_supply_relationships.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `communication_audit_events.metadata` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `communication_drafts.recipients` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `communication_drafts.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `component_classes.business_unit_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `component_classes.source_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `crm_activities.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `crm_companies.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `crm_contacts.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `crm_deals.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_canonical_programs.program_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_canonical_programs.promotion_provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_public_accounts.industries` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_public_accounts.account_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_public_accounts.source_identifiers` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `durable_public_accounts.promotion_provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `federal_opportunity_assessments.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `governed_explanations.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `intelligence_signals.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `market_refresh_runs.report` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `market_series_vintages.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_brief_syntheses.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_candidate_promotion_audits.promotion_provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_collection_runs.cursor` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_collection_runs.failures` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_collection_runs.funnel` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_entity_candidate_resolutions.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_event_clusters.observation_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_event_clusters.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_event_clusters.related_event_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_events.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_events.event_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_intelligence_assessments.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_observations.structured_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_organization_candidates.source_identifiers` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_organization_candidates.provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_organization_candidates.event_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_organization_candidates.observation_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_organization_candidates.candidate_account_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_program_candidate_promotion_audits.promotion_provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_program_candidates.provenance` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_program_candidates.event_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_research_runs.result` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_research_steps.result` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monitor_technical_decompositions.projection` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `monthly_commercial_history.source_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `omni_conversations.turns` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `omni_runs.result` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `orders.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `programs.source_payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `reference_field_import_runs.report` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `reference_field_versions.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `score_assessments.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `score_assessments.missing_fields` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `seller_itineraries.payload` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `work_audit_events.metadata` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `work_items.evidence_ids` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |
| `work_items.context_referents` | `TEXT` | `JSONB` | Structured object/list serialized as text | NEEDS_COORDINATED_CODE_CHANGE | B (integration) |

No `BOOLEAN_AS_STRING` declaration was found by scanning String columns named `is_*`, `has_*`, `can_*`, `active`, `enabled`, `synthetic`, `verified`, or `designated`. Six declared integer minor-unit money columns are **correct as integer storage**, not included in the 98 changes: `commercial_contexts.ttm_revenue_minor`, `commercial_contexts.ttm_bookings_minor`, `commercial_quotes.value_minor`, `monthly_commercial_history.revenue_minor`, `monthly_commercial_history.bookings_minor`, and `orders.amount_minor`. `modules/commercial/ledger.py` validates integer minor-unit fields and consistent currency within an account; `modules/commercial/money.py` divides USD minor units by 100 and does not claim the same scale for other currencies. A cross-currency convention is therefore **not established** by the model alone.

### SQL-accessed JSON columns

No SQL-level JSON operators found on any of the 85 columns; all can remain TEXT through Milestone A.

## Section 7 — Data provenance

This is an **intended source-path classification of 95 declared SQLAlchemy tables**, not a statement about rows in any database. Counts: **SAMPLE_FIXTURE 34; SYNTHETIC 0; LIVE_SOURCE 8; DERIVED 14; MIXED 29; READ_ONLY 0; DEAD 10; UNKNOWN 0**. “MIXED” includes user/application state and inputs with multiple allowed origins; “DEAD” means no SQLAlchemy table-object query use, while “READ_ONLY” means table-object use only in `select()`. A table reference means the SQLAlchemy table object is imported from persistence and used in a query. String matches, JSON keys, local variables, and response fields with the same name are not references. A table classified SAMPLE_FIXTURE can still be empty in the actual database, and a table classified LIVE_SOURCE is not proof of collected live rows. Retention is `NOT SPECIFIED` unless the source declares a concrete bound; no policy is invented.

Source/writer key (paths are relative to `backend/src/btx_omni/`): **SE** = `providers/sample/environment.py:109` plus `persistence/repository.py:20`; **CI** = `persistence/import_commercial_sample.py` and `persistence/commercial_import.py:66` (the versioned sample package under `docs/research/enriched_commercial_sample.json`); **MP** = `monitor/service.py:463` and `monitor/repository.py:527` (or the named repository save method); **PR** = `monitor/promotion.py`; **RJ** = `monitor/research_state.py`; **DA/DP** = `persistence/durable_accounts.py` / `durable_programs.py`; **AP** = `persistence/account_planning.py`; **WA** = `persistence/actions.py`; **AI** = `persistence/ai_usage.py`; **CM** = `persistence/communications.py`; **OC/OR/OM** = `persistence/omni_conversations.py` / `omni_runs.py` / `omni_memory.py`; **RF** = `persistence/reference_fields.py`; **IT** = `persistence/itineraries.py`; **WF** = `persistence/work_feedback.py`; **NI** = `persistence/network_import.py` plus the optional fake seed in `persistence/seed_network_sample.py`; **MS** = `persistence/market_series.py` (accepts provided or live public downloads). For DERIVED rows, the upstream is the corresponding Monitor event/observation, candidate, user action, conversation, or imported source table in the writer.

| Declared table | Source class | Loader/writer | Refresh pattern | Retention evidenced in source |
| --- | --- | --- | --- | --- |
| `account_partnership_audit` | MIXED | AP | APPEND_ONLY | NOT SPECIFIED |
| `account_partnership_designations` | MIXED | AP | MUTABLE | NOT SPECIFIED |
| `account_relationship_edges` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `accounts` | SAMPLE_FIXTURE | SE | IMMUTABLE seed | NOT SPECIFIED |
| `action_subtasks` | MIXED | WA | MUTABLE | NOT SPECIFIED |
| `action_suggestion_decisions` | MIXED | WA | MUTABLE | NOT SPECIFIED |
| `ai_call_receipts` | MIXED | AI | MUTABLE | NOT SPECIFIED |
| `assistant_turns` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `btx_facilities` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `bu_capabilities` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `commercial_acceptances` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_account_profiles` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_actions` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_agreements` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_alerts` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `commercial_cancellations` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_contacts` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_contexts` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_fulfillment_plans` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_import_ownership` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_import_runs` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_invoices` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_matches` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `commercial_order_lines` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_payments` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_quote_lines` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_quote_revisions` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_quotes` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_revenue_events` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_rfqs` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_role_targets` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_service_events` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_shipments` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `commercial_supply_relationships` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `communication_audit_events` | MIXED | CM | APPEND_ONLY | NOT SPECIFIED |
| `communication_drafts` | MIXED | CM | MUTABLE | NOT SPECIFIED |
| `component_classes` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `crm_activities` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `crm_companies` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `crm_contacts` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `crm_deals` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `durable_canonical_programs` | DERIVED | DP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `durable_public_accounts` | DERIVED | DA | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `external_industry_ranks` | SAMPLE_FIXTURE | SE | IMMUTABLE seed | NOT SPECIFIED |
| `facilities` | SAMPLE_FIXTURE | SE | IMMUTABLE seed | NOT SPECIFIED |
| `federal_collection_checkpoints` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `federal_opportunity_assessments` | DERIVED | MP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `governed_explanations` | DERIVED | MP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `identity_mappings` | SAMPLE_FIXTURE | SE | IMMUTABLE seed | NOT SPECIFIED |
| `intelligence_signals` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `market_refresh_runs` | MIXED | MS | APPEND_ONLY | NOT SPECIFIED |
| `market_series_current` | MIXED | MS | UPSERT pointer | NOT SPECIFIED |
| `market_series_vintages` | MIXED | MS | IMMUTABLE vintage | IMMUTABLE history; no expiry |
| `monitor_brief_syntheses` | DERIVED | MP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_candidate_promotion_audits` | DERIVED | PR | APPEND_ONLY | NOT SPECIFIED |
| `monitor_collection_runs` | LIVE_SOURCE | MP | APPEND_ONLY | NOT SPECIFIED |
| `monitor_entity_candidate_resolutions` | DERIVED | MP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_event_clusters` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_events` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_intelligence_assessments` | DERIVED | MP | MUTABLE/versioned | NOT SPECIFIED |
| `monitor_observations` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_organization_candidates` | DERIVED | MP+PR | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_program_candidate_promotion_audits` | DERIVED | PR | APPEND_ONLY | NOT SPECIFIED |
| `monitor_program_candidates` | DERIVED | MP+PR | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_rejected_observations` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_research_runs` | DERIVED | RJ | MUTABLE/versioned | NOT SPECIFIED |
| `monitor_research_steps` | DERIVED | RJ | MUTABLE/versioned | NOT SPECIFIED |
| `monitor_source_health` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_source_versions` | LIVE_SOURCE | MP | REPLACE_BY_KEY | NOT SPECIFIED |
| `monitor_technical_decompositions` | DERIVED | MP | UPSERT/REPLACE_BY_KEY | NOT SPECIFIED |
| `monthly_commercial_history` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `network_affiliations` | MIXED | NI | APPEND_ONLY import/purge | NOT SPECIFIED |
| `network_import_batches` | MIXED | NI | APPEND_ONLY import/purge | NOT SPECIFIED |
| `network_people` | MIXED | NI | APPEND_ONLY import/purge | NOT SPECIFIED |
| `network_ties` | MIXED | NI | APPEND_ONLY import/purge | NOT SPECIFIED |
| `network_unresolved_companies` | MIXED | NI | APPEND_ONLY import/purge | NOT SPECIFIED |
| `omni_chat_feedback` | MIXED | OC | MUTABLE | NOT SPECIFIED |
| `omni_conversations` | MIXED | OC | MUTABLE/expiry delete | 30 days (default) |
| `omni_memory_create_requests` | MIXED | OM | MUTABLE | receipt survives preference deletion |
| `omni_runs` | MIXED | OR | MUTABLE | NOT SPECIFIED |
| `omni_user_memory` | MIXED | OM | MUTABLE/expiry | TTL 1–365 days |
| `orders` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `paperless_accounts` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `programs` | SAMPLE_FIXTURE | CI | UPSERT by owned key | NOT SPECIFIED |
| `reference_field_current` | MIXED | RF | MUTABLE | NOT SPECIFIED |
| `reference_field_import_runs` | MIXED | RF | MUTABLE | NOT SPECIFIED |
| `reference_field_versions` | MIXED | RF | MUTABLE | NOT SPECIFIED |
| `score_assessments` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `score_configurations` | DEAD | — | UNVERIFIED | NOT DETERMINABLE |
| `seller_itineraries` | MIXED | IT | MUTABLE | NOT SPECIFIED |
| `seller_shortlist_items` | MIXED | AP | MUTABLE | NOT SPECIFIED |
| `user_preferences` | MIXED | CM | MUTABLE | NOT SPECIFIED |
| `work_audit_events` | MIXED | WA | APPEND_ONLY | NOT SPECIFIED |
| `work_items` | MIXED | WA | MUTABLE | NOT SPECIFIED |
| `work_suggestion_feedback` | MIXED | WF | MUTABLE | NOT SPECIFIED |

DEAD means the table is declared and migrated but not referenced by any current application code path. It does not mean the table should be dropped. Several DEAD tables correspond to features that may be connected during Milestone B (score_assessments, score_configurations, intelligence_signals, commercial_alerts, crm_contacts). The others are more likely drop candidates at Milestone B (account_relationship_edges, assistant_turns, btx_facilities, bu_capabilities, commercial_matches). Reclassify each at Milestone B when the BTX integration determines whether the table is wired up or dropped.

For the 14 DERIVED declarations, the upstream named by the writer is:

| Derived table(s) | Upstream table or input |
| --- | --- |
| `federal_opportunity_assessments` | Federal opportunity projection passed to `MonitorRepository.persist_federal_assessment`; no SQL-table upstream is required by that method. |
| `governed_explanations`, `monitor_brief_syntheses` | Governed assessment/brief inputs for a Monitor event; `monitor_events` and `monitor_intelligence_assessments` are the corresponding persisted context, but the writer accepts a projection argument. |
| `monitor_candidate_promotion_audits`, `durable_public_accounts` | `monitor_organization_candidates` and the confirmed promotion input in `monitor/promotion.py`; `durable_accounts.py` also accepts a direct connected-public-provenance create call. |
| `monitor_program_candidate_promotion_audits`, `durable_canonical_programs` | `monitor_program_candidates` and the confirmed promotion input in `monitor/promotion.py`; `durable_programs.py` also accepts a direct connected-public-provenance create call. |
| `monitor_entity_candidate_resolutions` | Entity-resolution projection supplied by the Monitor analysis path; no required SQL FK upstream. |
| `monitor_intelligence_assessments`, `monitor_technical_decompositions` | `monitor_events` and their observation/document context (`monitor_observations`); writers accept computed projections. |
| `monitor_organization_candidates`, `monitor_program_candidates` | `monitor_events` and `monitor_observations` supplied to `persist_snapshot`; promotion may update candidate review state. |
| `monitor_research_runs` | Event reference and source revision supplied to `MonitorResearchJournal.acquire`; a SQL FK to `monitor_events` is not declared. |
| `monitor_research_steps` | `monitor_research_runs` via `run_id` FK and step inputs in `research_state.py`. |

The ten `DEAD` declarations have no SQLAlchemy table-object query use in backend source. Similar names used for in-memory sample objects, API functions, JSON keys, local variables, or response fields do not reference these tables. An in-memory sample object is not evidence that a corresponding SQL table is seeded. Whether any table currently contains SAMPLE, SYNTHETIC, or LIVE rows remains pending database access.

## Section 8 — Verification script contract

**PENDING DATABASE ACCESS.** Phase 2 is not started; the generator contract and CI step will be handled with the database-dependent sections separately.
