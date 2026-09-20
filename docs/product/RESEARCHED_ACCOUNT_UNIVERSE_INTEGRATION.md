# Researched Account Universe Integration

**Historical integration checkpoint, superseded for current counts.** The numeric counts below describe the original input, not today's catalog. Use [generated catalog counts](SAMPLE_ENHANCEMENT_REPORT.md#generated-catalog-counts) and [Rubric v2.0](BTX_Omni_Scoring_Rubric_v2.0.md). The enhancement adds explicitly fictional organizations without promoting them to verified public identities.

## Inputs and validation

The supplied research directory contains `btx_researched_account_universe.json`, `btx_researched_contacts.json`, and `btx_research_integration_manifest.json`. The manifest references `_v2` filenames, but the supplied files omit that suffix. Their schema versions are 2.0, 2.0, and 1.0 respectively; the declared join key is `research_account_id`.

The ingestion loader rejects unsupported schemas, absent or duplicate research IDs, and contacts that reference an unknown research account. The historical input had 78 researched accounts, 80 named public contacts and 12 public contact channels; these are not current counts.

## Canonical mapping

The original researched identities formed that checkpoint's POC universe. Each canonical ID
is its `research_account_id`; no generated `Market Target` records, synthetic
public identities, synthetic coordinates, or simulated external ranks remain.
Curated scenarios attach simulated PRISM, Paperless, CRM, matching, alerts, and
scoring context to a subset of those real companies.

The research input is not asserted as a production market universe. A future
approved market-ranking methodology may be added as a separately governed feed.

## Truth and provenance

Each mapped account has VERIFIED PUBLIC identity fields and research provenance from the supplied source IDs and URLs. Public relationship evidence is separately represented: 3 `PUBLICLY_EVIDENCED_RELATIONSHIP`, 75 `NO_RELATIONSHIP_EVIDENCE`, and no `BTX_CONFIRMED` or `PUBLIC_INTERACTION_INFERENCE` records in this input. Public relationship evidence is explicitly replaceable by future approved BTX internal evidence.

Public identity and relationship evidence never convert the account's BTX relationship, PRISM, Paperless, CRM, cross-BU, or score inputs from SAMPLE/synthetic to connected data. Research priority is displayed as research context and is not an Account Attractiveness factor or external rank.

## Contact Research and Monitor

The canonical Contact Research section exposes 80 `NAMED_PUBLIC_CONTACT` records and 12 `PUBLIC_CONTACT_CHANNEL` records. Current verification totals are 21 `VERIFIED_OFFICIAL` and 71 `PUBLIC_PROFILE_VERIFIED`; all remain `RESEARCH_ONLY` and distinct from SAMPLE CRM and future HubSpot contacts. Role targets remain present for accounts without a named contact.

Generic Monitor profiles derive from supplied identities; see the generated current count in the enhancement report. Missing identifiers remain absent. The enhancement does not activate live monitors for its fictional organizations.

## Remaining work

Research coverage must grow toward defensible 100 real companies per industry. BTX must provide approved internal customer-master, PRISM, HubSpot, or Paperless evidence before a public relationship can become `BTX_CONFIRMED`; external rank methodology, further identifiers, facilities/geocodes, and publisher feeds remain open dependencies.
