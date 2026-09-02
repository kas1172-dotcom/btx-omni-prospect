# Phase 24A/B — Technical opportunity decomposition

Phase 24 adds a bounded public-evidence technical interpretation contract. It is
not a commercial score, supplier claim, or autonomous recommendation engine.

## Architecture

Gemini responsibilities:

- public technical-language interpretation;
- product/program extraction;
- system and subassembly decomposition; and
- manufactured component-candidate generation.

Deterministic Omni responsibilities:

- canonical identity;
- taxonomy normalization;
- controlled component matching;
- capability and Business Unit mapping;
- evidence provenance;
- eligibility, scoring, and authorization.

Each candidate explicitly carries `SOURCE_STATED` or `MODEL_INFERRED`. A
Gemini-inferred component is a technical hypothesis. A deterministic BTX taxonomy
match indicates governed capability alignment; neither asserts that BTX currently
supplies the product or program.

## Public evidence and caching

The contract accepts one to six distinguishable governed PUBLIC evidence records
(title, extract, URL, evidence ID, and provenance), preparing the system for
future bounded public-web research without treating one document as the only
source. One governed hash construction path hashes public evidence content and
IDs, event identity, deterministic canonical context, contract/prompt versions,
and model identity. The durable row stores that hash, provider/model metadata,
attempt count, retry time, and a seller-safe projection. Seller reads retrieve
the worker-owned row by event instead of guessing a runtime model. A changed
source, context, contract, prompt, or model does not reuse a cached result.
Seller read endpoints do not call Gemini.

## Deterministic matching

Only controlled `btx_component_taxonomy.json` classes and a small reviewed alias
set can produce `MATCHED`. Business Units come only from the matched controlled
component's taxonomy relation. Generic overlap produces
`POSSIBLE_MATCH_REVIEW_REQUIRED`; unsupported manufactured terms can be
`INSUFFICIENT_TAXONOMY`; unrelated terms are `NO_MATCH`. Gemini output cannot
provide BTX IDs, BU IDs, capability authority, canonical IDs, evidence, scores,
or relationships.

## Provider failure

The Monitor worker's bounded decomposition work is optional. `NOT_CONFIGURED`,
authentication, timeout, quota, and unavailable outcomes preserve the underlying
signal and persist an empty seller-safe technical opportunity rather than
fabricated technical fit. Durable AVAILABLE rows are reused; retryable failures
retain attempt count and use bounded status-specific cooldowns. Model evidence
IDs must be from the supplied governed PUBLIC evidence set. SOURCE_STATED
candidates require valid evidence and source support; Gemini cannot create
application evidence.
