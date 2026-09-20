# Map Rework Decision Log

## 2026-09-20 — Baseline

- Created branch `codex/map-rework` from the current branch.
- Preserved pre-existing Communications worktree changes; Map commits will stage explicit paths only.
- Baseline: frontend typecheck/lint/build/unit tests pass (90/90). Backend: 746 passed, 67 failed, 10 errors, 2 skipped.
- The 10 PostgreSQL journal errors are environmental because no local `BTX_DATABASE_URL`/PostgreSQL is available. Other existing failures remain comparison IDs in `MAP_REWORK_BASELINE.txt`.
- No dependencies added. No tests removed or modified in this step.

## 2026-09-20 — Step 0 findings

- Classified camera hypotheses in `MAP_REWORK_FINDINGS_2026-09-20.md` before application edits.
- Coordinate profiling uses the assembled SAMPLE runtime and `/api/map`; account coordinates are intentionally facility-scoped.
- Top 100 is an existing provenance-backed membership flag from the sanitized Top 100 workbook, not a rank. Decision: preserve it rather than derive a new trailing-revenue ranking, because replacing its semantics would alter data behavior outside Map.
- No dependencies added. No tests removed or modified in this step.
