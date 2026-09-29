# Open Investigations

## Test hygiene: direct `os.environ[...]` reads

Scope: tests that raise or skip differently when `BTX_DATABASE_URL` is absent because they read `os.environ["BTX_DATABASE_URL"]` directly. The intended separate cleanup is `.get()` with an explicit skip where a live database is required. Disposition: accepted test hygiene, not SAMPLE gate work.

Reopen when the SAMPLE gate or [baseline policy](TEST_BASELINE_POLICY.md) changes, or when CI changes whether `BTX_DATABASE_URL` is present.

## Configuration B collection errors

Scope: 23 collection errors observed with `BTX_COMMERCIAL_DURABLE_STATE_ENABLED=true`. Their cause requires a separate investigation. Disposition: unresolved release health, not SAMPLE failures.

Reopen for work touching durable commercial persistence or at the next full-suite diagnostic.
