# Phase 24C — Governed Explanation Service

## Purpose

Phase 24C adds concise seller-facing explanations to already-governed Omni Prospect results. It follows this sequence:

```text
deterministic Omni result
  → explicit domain adapter
  → bounded GovernedExplanationRequest
  → Gemini explanation or deterministic fallback
  → durable seller-safe projection
  → seller read
```

Gemini may explain a governed Omni Prospect result, but it cannot change the result, its evidence, its identity, or its authorization state.

## Supported explanations

The closed explanation type set is:

- `CUSTOMER_ATTRACTIVENESS` — Customer 360 score, factors, coverage, and missingness.
- `FEDERAL_OPPORTUNITY_RELEVANCE` — deterministic Federal relevance factors and calibration state.
- `TECHNICAL_OPPORTUNITY_FIT` — Phase 24A/B technical candidates and the resulting controlled match/BU projection.
- `RELATIONSHIP_PATH` — an already-selected, governed relationship path and its validation evidence.
- `SIGNAL_PRIORITY` — contract support exists, but seller-surface processing is deferred because current Monitor priority reasons are not yet exposed as one clean, bounded explanation input.

Today is also deferred. It already presents a backend-selected deterministic set, but a consolidated explanation would require a separate, explicit projection contract rather than an inference over the raw Monitor universe. Phase 24C does not redesign Today ranking or signal eligibility.

## Authority boundary

Gemini translates supplied facts into seller-readable language. It can summarize drivers, limitations, missingness, technical relevance, and an existing path. It cannot calculate or replace:

- Customer Attractiveness scores, factor values, coverage, or status;
- Federal Opportunity Relevance, eligibility, rank, PWin, award likelihood, or qualification status;
- technical decomposition provenance, controlled component matches, Business Unit mappings, or taxonomy;
- relationship edges, path order, validation state, strength, familiarity, or willingness to introduce;
- evidence IDs, canonical identity, supplier status, commercial facts, writes, or authorization.

For technical fit, a controlled BTX taxonomy match means capability alignment. It does not establish that BTX supplies, is incumbent on, or will win work for the program.

## Bounded contract and evidence

`GovernedExplanationRequest` accepts only explicit, bounded governed fields: explanation and subject context, deterministic result/status, numeric value and score unit where applicable, configuration version, drivers, limitations, deterministic matches, missingness, evidence IDs, data mode, and calibration/hypothesis state. The governed-content hash includes these inputs plus contract version, prompt version, style, and provider model where configured.

The model response has no replacement-score, rank, match, BU, identity, or authorization fields. Every returned evidence ID must already exist in the request. Unsupported evidence, malformed structured output, or a response for the wrong explanation contract is rejected and falls back safely.

External labels and public-source-derived content are treated as data, not instructions. The prompt instructs Gemini to ignore embedded instructions, use no tools, and perform no writes.

## Persistence, cache, and fallback

Migration `0020_governed_explanations` stores validated, seller-safe projections in `governed_explanations`; raw prompts and raw model JSON are not stored. The worker-owned processing path performs provider calls outside ordinary seller reads. Seller APIs only attach a persisted projection and never invoke Gemini.

An exact `AVAILABLE` result is reused durably. Changed deterministic content, evidence, prompt/contract version, model, score metadata, or explanation style produces a new governed hash and a new attempt sequence. `NOT_CONFIGURED` is durable and does not hot-loop. `AUTH_FAILED`, `TIMEOUT`, `QUOTA`, and `UNAVAILABLE` use bounded cooldowns with durable `attempt_count` and `next_retry_at` metadata. A failure returns and persists a deterministic fallback so the underlying seller surface remains usable.

Fallbacks use only deterministic result text, drivers, limitations, matches, missingness, and governed evidence. Missing data remains uncertainty: unavailable Prism revenue, Paperless quotes, or HubSpot activity does not mean no relationship, poor performance, or no fit.

## Seller presentation

The shared accessible disclosure appears after the primary deterministic result:

- **Why this Customer stands out** in Customer 360.
- **Why this opportunity is relevant** in Federal Procurement.
- **Why this technical fit may matter** in Potential BTX Technical Fit.
- **Why this relationship path may be useful** in selected Relationship Intelligence graph details.

When Gemini is unavailable, the same disclosure renders the governed fallback without claiming Gemini assistance. Internal provider, hash, retry, and raw-output details are not shown in normal seller UI.

## Deliberate exclusions

Broad public-web research and search grounding remain Phase 24D work. Gemini communication drafting remains later work (Phase 24E). This phase does not add autonomous browsing, ranking, customer selection, communication delivery, or taxonomy mutation.
