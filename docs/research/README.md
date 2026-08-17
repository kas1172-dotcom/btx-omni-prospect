# BTX Sample Data Research — Master Index

**Generated:** 2026-08-17
**Purpose:** Replace the current `docs/research/*.json` content with a BTX-weighted, evidence-linked customer universe plus the additional catalogs the console needs to run realistic scenarios end-to-end.
**Delivered in three batches:** foundational reference catalogs (this batch), replaced core-schema files (batch 2), simulated commercial layer (batch 3).

## Why this replacement matters

The current `docs/research/` universe is 78 large public-market companies (Boeing, Lockheed, Intel, TSMC, Applied Materials, etc.). That set is **prospecting-oriented, not BTX-weighted**. Only one account (Boeing) carries an explicit BTX-supplier basis (via Chandler Industries' public defense page). Every other relationship is `NO_RELATIONSHIP_EVIDENCE`. Sellers cannot see themselves in this universe.

The manifest's own vision statement calls for "the final 600 real account universe" (100 real companies × 6 industries). That's the target. This replacement is the first material step toward it: a BTX-weighted customer set built from BTX Precision's own business-unit websites, industry pages, case studies, press releases, and third-party award profiles, with public contact channels sourced from official supplier portals.

## What BTX Precision actually is (research summary)

BTX Precision is a PE-backed precision-manufacturing holding platform owned by L Squared Capital Partners since June 2023 (starting with ERA Industries). As of April/May 2026 it operates 8+ business units and ~1,200 employees across 700,000+ sq ft in 13 production units, serving aerospace, defense, space, medical, semiconductor, and energy.

Leadership:
- **Rick McIntyre** — Group CEO (named January 2024)
- **Michael Fennerty** — Group CFO (named March 2024)
- **Jamie Goettler** — Group CRO (named May 2024) — *the Jamie you're building this with*
- **Randall Hunt** — Managing Partner at L Squared, BTX board member

Confirmed business units with sources:
1. **ERA Industries** (Chicago area; parent brand's founding acquisition; Director of Aerospace and Defense **Gene Kline**)
2. **Gen-El-Mec Associates** (US, complex CNC milling/turning)
3. **i3D MFG** (Oregon; direct metal laser sintering, only DMLS-focused BU; recently acquired Burloak Technologies)
4. **Addison Precision Manufacturing / APM** (Rochester NY; ultra-tight tolerances)
5. **A1J Technologies** (Bay Area; formed from 5 acquired companies including A-1 Jay's Machining, A-1 Jay's Sheet Metal, Inotech Laser, Bay Area Grinding, Silicon Valley Precision Cleaning; ISO 13485 + ISO Class 5 Cleanroom + CMMC)
6. **Chandler Industries** (Blaine/Montevideo/Long Prairie MN, Lake Mills WI, Wyoming, Chihuahua MX; founded 1962 by **Chandler Olson**; 5 facilities, 213K sq ft, 370+ employees; recently acquired Arrow Engineering and Aztalan Engineering)
7. **High Tech Solutions / HTS** (Kansas City area; newest BTX acquisition August 2025)
8. **Maitland Engineering** (South Bend IN + Coon Rapids MN; Swiss CNC; medical/orthopedic-focused; ISO 13485; metadata evidence points to Zimmer/Biomet as customers)

MATCH platform (**M**achining **A**dditive **T**echnology and **C**apabilities **H**ub) launched November 2025 as a customer-facing capabilities portal at `capabilities.btxprecision.com`.

## Files in this research package

### Batch 1 — Foundational reference catalogs (this batch)

| File | Purpose | Consumed by |
|---|---|---|
| `README.md` | This file. Master index and how to use. | Humans |
| `CODEX_INSTRUCTIONS.md` | Change/delete list for the codebase. Anchored to files below. | Codex agent |
| `btx_company_profile.json` | BTX Precision identity, 8 BUs, leadership. NEW — no existing equivalent. | New: `providers/research/btx_profile.py` (Codex creates) |
| `btx_program_catalog.json` | Real programs BTX customers work on (F-35, Artemis, NGAD, Starship, CLPS, etc.). NEW. | Existing `domain/programs.Program` dataclass; new persistence table `programs` |
| `btx_component_taxonomy.json` | BTX-relevant part families and component classes. NEW. | Existing `domain/programs.ComponentClass`; new table `component_classes` |
| `btx_capability_catalog.json` | Per-BU capabilities (materials, processes, tolerances, certifications). NEW. | Existing stub `domain/capabilities.Capability`; new table `bu_capabilities` |
| `btx_relationship_edges.json` | Cross-account edges (shared programs, shared prime contractor, parent-subsidiary). NEW. | New model `account_relationship_edges` per audit section 8 |

### Batch 2 — Replaced content for existing schema files (next turn)

| File | Purpose | Replaces |
|---|---|---|
| `btx_researched_account_universe.json` | ~30 BTX-relevant customers with rich detail. | Existing 78-account file (schema preserved) |
| `btx_researched_contacts.json` | Named contacts + public channels for the new customer set. | Existing 80-contact file (schema preserved) |
| `btx_public_facility_feed_enrichment.json` | HQ and facility data for the new customer set. | Existing facility file (schema preserved) |
| `btx_usaspending_recipient_identities.json` | USAspending recipient legal-name mappings for federal-contracting customers. | Existing 11-mapping file (schema preserved) |
| `btx_research_integration_manifest.json` | Updated manifest pointing to the new files, with new integration boundaries. | Existing manifest |

### Batch 3 — Simulated commercial layer (subsequent turn)

| File | Purpose | Consumed by |
|---|---|---|
| `btx_sample_paperless_quotes.json` | ~50 simulated Paperless quotes matching real Paperless API shape. | New table `commercial_quotes` |
| `btx_sample_orders.json` | ~30 simulated orders (transaction-level, for overdue-order alerts). | New table `orders` |
| `btx_sample_commercial_context.json` | Monthly customer × BU revenue/bookings for ~10 accounts × 12 months × 2 BUs. Lake-shape. | New table `commercial_context` |
| `btx_sample_hubspot_crm.json` | Companies/contacts/deals/activities in HubSpot v3 default-property shape. | New tables `crm_companies`, `crm_contacts`, `crm_deals`, `crm_activities` |

## How ingestion consumes these files

The current `providers/research/ingestion.py` reads five files at startup. After this replacement:

- **No code change is required** in `ingestion.py` for the five schema-preserved files (batch 2). The schema versions (`2.0` for universe, `2.0` for contacts, `1.0` for facility, `1.0` for USAspending, `1.0` for manifest) stay identical.
- **New loaders required** for the new files (batches 1 and 3). Codex builds them per `CODEX_INSTRUCTIONS.md`. The dataclasses these load into already exist in `domain/` (Program, ComponentClass, Capability, CommercialQuote, CommercialContext, etc.).
- **New Alembic migration required** (`0008_commercial_and_edges.py`) to add tables for the domain concepts that currently only exist as dataclasses in memory: `programs`, `component_classes`, `bu_capabilities`, `btx_facilities`, `commercial_contexts`, `monthly_commercial_history`, `commercial_quotes`, `paperless_accounts`, `orders`, `account_relationship_edges`, `crm_companies`, `crm_contacts`, `crm_deals`, `crm_activities`.

## Truth boundaries preserved

Every research assertion in the JSON files carries source URLs and evidence state. Public facts stay marked `VERIFIED_PUBLIC` with source lineage. BTX-internal facts (quotes, orders, commercial context, CRM state) stay marked `SIMULATED_POC` with synthetic provenance and `SAMPLE` data mode. Nothing pretends to be BTX-confirmed unless a public source (BTX BU website, press release, award profile, government contract) supports it.

## Sources used in this research pass

- **BTX Precision:** btxprecision.com (homepage, business-units, case-studies, certifications, press, corporate-profile, industry pages for aerospace/defense/space/medical/semiconductor/energy)
- **Business unit sites:** eraind.com, chandlerindustries.com, a1jt.com, maitlandengineering.com, i3dmfg.com, addisonprec.com
- **Third-party award profiles:** manufacturingtechnologyinsights.com/era-industries (Top Defense Manufacturing Solutions Provider 2024)
- **Trade press:** aerospace-trends.com, businesswire.com, pulse2.com, thefabricator.com
- **PE / financial:** lsquaredcap.com, pitchbook, cbinsights, privsource
- **Government sources for supplier evidence:** existing `docs/research/*.json` files already have Lockheed RMS procurement, Lockheed supplier portal, RTX, Raytheon, Boeing, Honeywell, SpaceX, NASA — preserved and augmented
- **LinkedIn (public, Google-indexed only):** BTX Precision leadership profiles for Jamie Goettler, Michael Fennerty; BU announcements

## Contact research ethics

Every contact in batch 2:
- Is either a named individual verifiable from an official public source (company procurement portal, SEC filing, government release, official press release, conference speaker page), OR
- Is a role-family target (procurement, supply chain, supplier management, engineering, manufacturing, operations) when a named person is not publicly identifiable.
- No LinkedIn scraping. Google searches of publicly-indexed LinkedIn snippets are used only to surface names that appear in official-source verification checks.
- No personal contact info (personal phone, personal email).
- No fabricated individuals.

This matches the existing `named_public_contact` vs `public_contact_channel` vs `role_target` truth-rules in the current `docs/research/btx_researched_contacts.json`.

## What this changes about the scoring rubric (feed-in to design brief)

The workflow spec noted the scoring rubric is a working draft, and research findings surface these candidate revisions:

1. **BTX manufacturing fit should decompose by BU.** With 8 BUs each having distinct capabilities (i3D is DMLS-only; A1J has cleanroom + medical; Chandler has 5 facilities + medical + aerospace; Maitland is Swiss CNC medical), a single "material match / process match" bin misses that a customer might be a great fit for Maitland but a mismatch for i3D. Recommend: score fit per BU × customer, then roll up.
2. **BTX commercial adjacency should count active BUs, not just presence.** Currently the rubric asks "multi-BU active" vs "one BU active" — but with 8 BUs, a 2-BU customer is very different from a 6-BU customer. Consider a continuous score based on BU count.
3. **Capacity fit belongs in the rubric.** Currently excluded ("proximity is seller planning input only"). But per Alan, capacity is derived from production history and matters a lot. Recommend adding a Capacity Fit sub-factor to BTX Manufacturing Fit.
4. **Program-durability program list should come from the program catalog.** Currently the rubric asks "10+ years, 5-9, 2-4" but has no reference for which programs qualify. The `btx_program_catalog.json` (batch 1) supplies that reference.

These feed into the design brief conversation.

## Where the "600 overly general accounts" concern comes from

The current manifest states: `"data_complete_for_final_600_real_account_universe": false`. Your instinct was right that 600 was the target; the current file has 78. This replacement moves toward that target with ~30 rich BTX-relevant accounts in batch 2, not 600, because rich detail matters more than count for POC credibility. Growing to 600 is a subsequent research phase against the same schema.

## Next steps in the sequence

1. Review batch 1 (this).
2. I deliver batch 2 (replaced core-schema files).
3. I deliver batch 3 (simulated commercial layer).
4. We draft the design brief for Alan using the workflow spec + this research.
5. Codex executes `CODEX_INSTRUCTIONS.md` against the codebase.
