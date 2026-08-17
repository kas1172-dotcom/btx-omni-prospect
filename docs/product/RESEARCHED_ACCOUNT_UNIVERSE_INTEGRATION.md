# Researched Account Universe Integration

## Inputs and validation

The supplied research directory contains `btx_researched_account_universe.json`, `btx_researched_contacts.json`, and `btx_research_integration_manifest.json`. The manifest references `_v2` filenames, but the supplied files omit that suffix. Their schema versions are 2.0, 2.0, and 1.0 respectively; the declared join key is `research_account_id`.

The ingestion loader rejects unsupported schemas, absent or duplicate research IDs, and contacts that reference an unknown research account. The current input has 78 unique researched accounts, 80 named public contacts, 12 public contact channels, and no duplicate research IDs.

## Canonical mapping

The 78 researched identities are the canonical POC universe. Each canonical ID
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

78 generic Monitor watch profiles are activated from supplied public identity data only. They carry legal name, supplied aliases, domain, and industry; missing CIK, ticker, newsroom, IR, facilities, and other identifiers remain absent. Exact legal-name resolution is enabled; alias, ambiguous, and unresolved resolution remain governed by the common resolver.

## Remaining work

Research coverage must grow toward defensible 100 real companies per industry. BTX must provide approved internal customer-master, PRISM, HubSpot, or Paperless evidence before a public relationship can become `BTX_CONFIRMED`; external rank methodology, further identifiers, facilities/geocodes, and publisher feeds remain open dependencies.
