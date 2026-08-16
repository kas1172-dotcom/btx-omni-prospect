# Market universe identity audit

Audited 2026-08-16 against the canonical SAMPLE provider. The 600-account
market universe is a deterministic POC market layer, not a verified public
company directory. Every account carries `sample-environment` provenance,
`data_mode=SAMPLE`, `synthetic=true`, and a `sample.invalid` domain.

## Classification results

| Industry | REAL_VERIFIED_COMPANY | REAL_COMPANY_NEEDS_ENRICHMENT | SYNTHETIC_PLACEHOLDER | AMBIGUOUS | Public/private verified |
|---|---:|---:|---:|---:|---|
| Commercial Aerospace | 0 | 0 | 100 | 0 | Not applicable |
| Defense | 0 | 0 | 100 | 0 | Not applicable |
| Space | 0 | 0 | 100 | 0 | Not applicable |
| Semiconductor | 0 | 0 | 100 | 0 | Not applicable |
| Medical Device | 0 | 0 | 100 | 0 | Not applicable |
| Robotics | 0 | 0 | 100 | 0 | Not applicable |
| **Total** | **0** | **0** | **600** | **0** | **0 verified** |

The 17 deep scenario accounts are also synthetic. Their PRISM, Paperless, CRM,
relationship, cross-BU, score-input, and facility-planning facts remain SAMPLE
POC data and must not be used as public identity evidence.

## Public identity contract

`PublicCompanyIdentity` and `PublicIdentityField` preserve a separate public
identity attestation on a canonical account. Verified fields require
non-synthetic `CONNECTED` public provenance, source-native identifier support,
and `last_verified_at`. Supported field states are
`VERIFIED_AUTHORITATIVE`, `VERIFIED_OFFICIAL_PUBLISHER`, `INFERRED`,
`AMBIGUOUS`, `UNVERIFIED`, and `NOT_APPLICABLE`.

No identity attestation has been attached to the current 600 accounts. This is
intentional: attaching real CIKs, domains, company URLs, aliases, subsidiaries,
or public facilities to synthetic names would create false canonical links.

## Ranking truth

Each account has a deterministic SAMPLE external rank labelled `SAMPLE Top-100
methodology`; it remains explicitly separate from Account Attractiveness. Its
real-world source and methodology are **UNVERIFIED**. BTX/Jamie must approve the
ranking publisher, methodology, industry classification, and refresh cadence
before a public rank may be claimed as verified.

## Required enrichment input

BTX must provide an approved real-company market-universe feed or reviewed
canonical identity mappings before this audit can classify any account as real.
For each candidate, retain authoritative source URL/reference, verification
date, source-native identifiers, official domain/IR/newsroom URLs, and any
parent/subsidiary/facility relationship. A subsidiary must remain distinct from
its parent unless a governed relationship explicitly supports it.
