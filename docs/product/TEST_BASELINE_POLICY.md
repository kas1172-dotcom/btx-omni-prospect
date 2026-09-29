# Test Baseline Policy for Demo SAMPLE

The isolated SAMPLE gate is the merge contract for demo-only sample convergence. Its frozen result is **92 passed / 0 failed / 0 errors**. The full backend suite is informational release-health reporting: categorize its failures, but they do not block SAMPLE convergence unless they affect this gate. **The gate is the exact pytest invocation below**, not a marker or a fixed count of test files; the number 92 describes one run of that invocation.

## Gate membership and reproducible command

Run from `/Users/kapilsharma/Desktop/btx-sample-convergence/backend` with the explicit task-owned database at Alembic revision `0042_merge_actions_network_chat`. The database URL contains no password. The reused virtual environment contains an editable install from another worktree, so the explicit `PYTHONPATH` is required to load this branch's code. No tracked `.env` is required.

```bash
cd /Users/kapilsharma/Desktop/btx-sample-convergence/backend
export BTX_DATABASE_URL='postgresql+psycopg://kapilsharma@localhost:5432/btx_omni_sample_convergence_20260928_r2'
export BTX_COMMERCIAL_DURABLE_STATE_ENABLED=false
export PYTHONPATH='/Users/kapilsharma/Desktop/btx-sample-convergence/backend/src'
/Users/kapilsharma/Desktop/btx-omni-prospect/backend/.venv/bin/alembic current
/Users/kapilsharma/Desktop/btx-omni-prospect/backend/.venv/bin/pytest -q --tb=no \
  tests/test_sample_*.py \
  tests/test_release_sample.py \
  tests/test_poc_contracts.py \
  tests/test_priority_customer_completeness.py \
  tests/test_sanitized_reference_data.py \
  tests/test_app.py \
  tests/test_map_workspace.py
```

The shell expands `tests/test_sample_*.py` to the matching files at run time. A newly added matching file enters the gate automatically; a new file outside that pattern must be added explicitly. At this snapshot, the glob expands to:

- `test_sample_award_confidence.py`, `test_sample_data_contract.py`, `test_sample_enhancement_api.py`, `test_sample_enhancement_ledger.py`, `test_sample_enhancement_preflight.py`, `test_sample_environment.py`, `test_sample_expansion.py`, `test_sample_external_risk.py`, `test_sample_golden_tier1.py`, `test_sample_golden_tier2.py`, `test_sample_journey_contracts.py`, `test_sample_kratos.py`, `test_sample_medical_market.py`, `test_sample_model_budgets.py`, `test_sample_planning.py`, `test_sample_provider_foundation.py`, `test_sample_public_research.py`, `test_sample_regional.py`, and `test_sample_relationships.py`.

The six explicitly named files cover the release SAMPLE journey, POC contracts, and the four carried Phase 0.5 tests. Broad canonical API, durable commercial, monitor-worker, and migration-contract tests remain in the full suite. Their exclusion does not imply they pass.

## Current full-suite snapshot (informational, not gating, not canonical)

Configuration A uses the same exports and migration revision above, with `BTX_COMMERCIAL_DURABLE_STATE_ENABLED=false`. From the same `backend` directory, run:

```bash
/Users/kapilsharma/Desktop/btx-omni-prospect/backend/.venv/bin/pytest -q --tb=no
```

Result: **1,070 passed / 19 failed / 10 errors / 2 skipped** (14 warnings). This is a snapshot of the command and configuration above, not a regression or improvement claim.

The 19 failures group by test module and concern: 11 durable commercial catalog, import, or promotion acceptance cases (`test_account_planning`, `test_api_acceptance`, `test_candidate_promotion`, `test_commercial_persistence`, `test_crm_mapping_preservation`, `test_durable_canonical_programs`, `test_durable_public_accounts`, `test_program_candidate_promotion`); three monitor-worker cases (`test_monitor_discovery_acceptance`, `test_monitor_live`, `test_monitor_operations`); and five network route authorization cases (`test_network_route_inventory`). These groups remain release-health issues outside the SAMPLE gate.

The discrepancy with the discussed 1,080/19/0 diagnostic is a **fixture database-name guard in this documented configuration**. With `BTX_DATABASE_URL` set, `test_monitor_research_journal.py` collects ten PostgreSQL parameterizations, but its `journal` fixture asserts that the database name is exactly `btx_omni` or starts with `btx_omni_e2e`. The documented task-owned database is `btx_omni_sample_convergence_20260928_r2`, so all ten stop at fixture setup. A direct rerun of `test_completed_run_replay_reuses_steps_without_provider_call[postgresql]` reproduced `AssertionError` at `backend/tests/test_monitor_research_journal.py:28`. Thus the 1,070/19/10 snapshot is the reproducible result for the URL above; the 1,080/19/0 figure is not a result of this configuration, and this document makes no claim that the ten tests pass under another URL. This fixture setup issue does not affect the SAMPLE gate.

## Historical full-suite snapshots (informational, not canonical)

These figures came from different worktrees, configurations, or intermediate edits. They are not reproducible from the current state and must not be used as reference points for a future delta:

- 749 passed / 55 known failures (original, retired).
- 1,068 passed / 33 failed / 10 errors / 7 skipped (early Phase 0).
- 1,068 passed / 33 failed / 0 errors / 7 skipped (later Phase 0).
- 1,099 passed / 16 failed / 0 errors / 2 skipped / 1 strict xfail (Phase 0.5, retired).
- 1,068 passed / 29 failed / 0 errors / 2 skipped / 1 strict xfail (isolated pre-Phase-1 view).
- 1,070 passed / 19 failed / 10 errors / 2 skipped (intermediate post-Phase-1 view).
- 1,051 passed / 38 failed / 0 errors / 2 skipped (a run without `BTX_DATABASE_URL`).
- 1,080 passed / 19 failed (proposed as configuration A in discussion; not established as canonical).

The earlier **749/55** and **1,099/16** baselines are explicitly retired. The only canonical count here is the scoped SAMPLE gate's 92/92 result. See [open investigations](OPEN_INVESTIGATIONS.md) for release-health follow-ups.
