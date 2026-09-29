# SAMPLE Convergence Test Scope

This gate proves the demo-only SAMPLE environment is internally coherent. It
covers SAMPLE runtime construction, sample providers and fixtures, provenance
and labeling, sample scenarios and journeys, sample projections, and the
four carried Phase 0.5 tests where they assert current SAMPLE behavior.

The merge policy and frozen result are maintained in
[TEST_BASELINE_POLICY.md](TEST_BASELINE_POLICY.md). The explicit source path
below is required when reusing the virtual environment from the shared
repository.

The scoped command is:

```bash
cd backend
export BTX_DATABASE_URL='postgresql+psycopg://kapilsharma@localhost:5432/btx_omni_sample_convergence_20260928_r2'
export BTX_COMMERCIAL_DURABLE_STATE_ENABLED=false
export PYTHONPATH='/Users/kapilsharma/Desktop/btx-sample-convergence/backend/src'
/Users/kapilsharma/Desktop/btx-omni-prospect/backend/.venv/bin/pytest -q \
  tests/test_sample_*.py \
  tests/test_release_sample.py \
  tests/test_poc_contracts.py \
  tests/test_priority_customer_completeness.py \
  tests/test_sanitized_reference_data.py \
  tests/test_app.py \
  tests/test_map_workspace.py
```

Broad API acceptance, durable commercial persistence, monitor-worker, and
release/migration-contract tests remain in the full release-base suite. They
are intentionally outside this gate because they exercise contracts or
infrastructure beyond demo-only sample convergence. Exclusion does not imply
those tests pass; the full suite must still be reported separately.

The structured SAMPLE fields are authoritative for membership and provenance.
Tests must not require brittle prose phrases when the API already exposes the
governed structured values.
