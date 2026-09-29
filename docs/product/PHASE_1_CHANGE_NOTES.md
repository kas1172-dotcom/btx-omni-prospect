# Phase 1 Change Notes

The demo-only SAMPLE convergence work made enhanced SAMPLE composition permanent, removed the enhancement flag, documented the runtime fixture boundary, clarified the research/import distinction, and added the SAMPLE data contract with a count-enforcement test. The September 28 audit was preserved as a separate audit record. CONNECTED behavior and safety boundaries were outside the change.

## Top 100 contract-test cleanup

`backend/tests/test_sanitized_reference_data.py` keeps the structured `btx_top_100` and truth-state assertions and no longer requires three exact phrases in Omni prose. Structured fields are authoritative for the SAMPLE contract. **Process caveat:** owner confirmation was not recorded before the initial assertion edit. The owner subsequently chose to keep the change; that later decision does not retroactively supply the missing prior confirmation.

## Strict xfail removal

The former strict xfail for the map projection was removed. The expected failure condition no longer applies under permanently enhanced SAMPLE behavior, and the test passes legitimately. The owner accepted this removal. No marker is restored.

The merge policy and reproducible test selection are in [TEST_BASELINE_POLICY.md](TEST_BASELINE_POLICY.md).
