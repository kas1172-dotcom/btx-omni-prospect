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
source. The worker-only service hashes public evidence, evidence IDs, contract
version, prompt version, and model identity. A changed source or contract version
does not reuse a cached result. Seller read endpoints do not call Gemini.

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
signal and are surfaced as provider state rather than fabricated technical fit.
