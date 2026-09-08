# Commercial SAMPLE import

This imports only the reviewed eleven-account scenario into existing canonical identities. It does not collect public Monitor events, create external CRM records, send messages, delete unrelated records, or run automatically at application startup.

Runtime source: `docs/research/enriched_commercial_sample.json`, byte-identical to the v3.3-R1 enriched input. SHA-256: `7745ab0d8d8b73d27452cb4302979440453587eaeb1c9e1512a4750b8570c493`. Account-only crosswalk and domain checks are in `btx_omni.persistence.import_commercial_sample`; facilities, components and programs retain distinct identities. Historical baseline data is not imported a second time.

Prerequisites: correct repository/release identity, Python 3.11 with the frozen lock, SAMPLE mode, verified PostgreSQL host/database, qualified migration `0027_memory_create_receipts`, and a recoverable backup for a deployed destination. Database credentials come from existing protected configuration; never put them in a report or client bundle.

From `backend`, first dry-run against the explicitly reviewed destination:

```sh
uv run python -m btx_omni.persistence.import_commercial_sample --expected-host VERIFIED_HOST --expected-database VERIFIED_DATABASE
```

Review the reported identity list, input hash, counts and `prior_revision`. Applying requires that exact revision; the importer checks it again inside its transaction after taking the import lock:

```sh
uv run python -m btx_omni.persistence.import_commercial_sample --expected-host VERIFIED_HOST --expected-database VERIFIED_DATABASE --apply --expected-revision REVIEWED_PRIOR_REVISION
```

Repeat the dry-run and verify zero created/updated/removed records. Read all accounts through the actual API, restart the backend, then repeat reads and reconciliation. Keep run IDs, revisions and backup references externally. A successful import does not qualify the full product or authorize bypassing release checks. Code rollback does not undo schema changes.

Corrected source records require a reviewed new runtime hash/release, dry-run and compatible ownership checks. A changed database revision invalidates an earlier review; do not retry with an invented revision or reset the database.
