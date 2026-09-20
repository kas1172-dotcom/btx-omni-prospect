# SAMPLE enhancement report

Status: implementation in progress; no tier certified complete yet.

## Decisions made without user input

1. Used the existing isolated `C:/Users/Aruna/btx-sample-data-enhancement` worktree and branch. Unrelated changes in the original worktree are untouched.
2. Imported the complete supplied Downloads rubric DOCX to Markdown, preserving the original text and tables. The DOCX lacks the promised R1–R10 preamble; explicit user amendments are recorded separately and override its erroneous examples. R9–R10 text is NOT FOUND and has not been invented.
3. Kept the earlier preflight checkpoint as historical evidence, with a superseding status section. The nine-day Signal Confidence target is now 86.25, not 85.75.
4. Baseline backend execution uses the existing Python interpreter with this worktree's `src` first on the import path, an ephemeral SQLite URL, disabled monitor/AI configuration and an audit hook prohibiting socket connections. Existing app/test code can load protected reference files; their contents are not logged or used as new fixture source material.

## Specification precedence

[Rubric v2.0](BTX_Omni_Scoring_Rubric_v2.0.md), including explicit user amendments, supersedes `docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`. Historical docs describing proportional reweighting do not specify current behavior. Executive deck slide 15's Action Priority weights and inverse-resilience internal risk formula are superseded by sections 8 and 13.

## Validation

### Scoring alignment (amendment 2)

| Owner | Before | After / authority |
|---|---|---|
| `families.assess` | No explicit evidence state; version V2 | V2.0 version on assessments; Stale/Unknown/Conflicting factors contribute no known points; historical IDs retained; section 2 fixed-weight ranges |
| `public_rules`, `public_inputs` | API factor named reversibility despite mitigation bins | Mitigation key throughout; section 7/R3. Existing `risk_mitigation` leaf inputs map unchanged: unavailable=100, no plan=75, not started=50, underway=25, fully mitigated=0. No invented translation of ambiguous legacy prose |
| `public_risk_assessment` | Stale observations retained numeric risk | Expired public risk becomes Unknown with 0–100 range, retained history and no escalation disposition; R1 |
| `health_inputs`, `risk_inputs` | No snapshot expiry | Explicit snapshot observation dates expire transaction factors after two days; employment/access after 30, structural history after 180; R6. Historical transaction age does not erase longitudinal history when freshly reviewed |
| pursuit inputs, qualification gates, commercial observations | Same-day review only | Evaluate dated review against as-of and the applicable 2/30-day window; sections 3, 6, 11, 12 |
| `customer_risk_projection` | Could not forward convergence/override evidence | Explicit optional evidence IDs forwarded; absent inputs produce no uplift/override; R8 |
| `families.assess` | No generic band/counterfactual fields | Add rule version, weighted score/band (including blocked cases), displayed band and factor-specific counterfactuals; sections 12/15 |
| `prospect_fit_projection` | Default evaluation frozen at provenance timestamp | Default evaluation uses the configured clock; explicit historical replay remains supported |

No replacement of the already-correct direct Internal Commercial Risk or triage-class Action Priority formulas. No schema migration or integration-stub changes. The generic API stores factors in dictionaries, so no closed frontend reversibility field existed to rename.

Test changes: the two strict xfails now assert the corrected passing targets (amended section 4 and R3). `test_scoring_v2_completion` checks `mitigation` instead of the retired key, justified by section 7. No test is deleted or weakened. Focused scoring suite: **88 passed** before fixture work. Frontend baseline: typecheck, lint and build passed.

The original no-socket baseline guard was too broad for Windows asyncio's loopback self-pipe. That run was interrupted and is not a valid product baseline. Revised isolation allows loopback only. Its first actual failing assertion concerns the older August cross-BU scenario after the clock shift; fixtures must be integrated before judging final regressions.

### Item 1.1 clock

Added `core/clock.py`, with fixed configurable `DEMO_AS_OF_DATE=2026-09-20`, inclusive expiry and relative fixture dates. Runtime observations previously used August 31; Today mixed that with wall-clock public evaluation. Both now use the provider. Public brief evaluation and catalog provenance default to the same clock. Explicit timestamps remain supported for historical replay. Authentication, provider accounting and retry timers remain operational clocks, not evidence-age clocks.

`test_demo_clock.py`: 2 passed. Covers advancing evaluation beyond the two-day expiry while preserving the observation, plus a wall-clock prohibition across scoring and provider fixture modules. Additional plumbing remains part of scoring alignment and fixture integration.

Previous checkpoint: focused baseline 73 passed; preflight probes 80 passed, 2 expected failures. Full-suite baseline is being established with the user-approved reference-file loading policy. Tier tags will only be created after verification.
