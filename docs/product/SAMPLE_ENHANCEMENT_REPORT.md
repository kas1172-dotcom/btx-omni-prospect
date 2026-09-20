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

### Item 1.1 clock

Added `core/clock.py`, with fixed configurable `DEMO_AS_OF_DATE=2026-09-20`, inclusive expiry and relative fixture dates. Runtime observations previously used August 31; Today mixed that with wall-clock public evaluation. Both now use the provider. Public brief evaluation and catalog provenance default to the same clock. Explicit timestamps remain supported for historical replay. Authentication, provider accounting and retry timers remain operational clocks, not evidence-age clocks.

`test_demo_clock.py`: 2 passed. Covers advancing evaluation beyond the two-day expiry while preserving the observation, plus a wall-clock prohibition across scoring and provider fixture modules. Additional plumbing remains part of scoring alignment and fixture integration.

Previous checkpoint: focused baseline 73 passed; preflight probes 80 passed, 2 expected failures. Full-suite baseline is being established with the user-approved reference-file loading policy. Tier tags will only be created after verification.
