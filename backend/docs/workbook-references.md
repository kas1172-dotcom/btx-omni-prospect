# Private original workbook references

`providers/research/reference_data.py` owns the reviewed, checksum-pinned normalized
runtime appendix `docs/research/btx_original_workbook_references.json`. Original
workbooks remain outside the repository. The public sanitized reference importer
is unchanged. This appendix never updates account identities, geography,
commercial totals, public claims or official scores.

Migration `0028_private_reference_fields` adds immutable source-row versions,
replacement-key current pointers and import receipts. Existing canonical account
IDs are validated before import; no accounts are created. Exact workbook/sheet/
row/column/header and source SHA are retained, including explicit nulls. Legacy
TTM May 2026 revenue keeps its original unit/period; it is not demo August TTM.
Four original phone formula caches are retained as invalid, not phone numbers.

Run `python -m btx_omni.persistence.import_reference_fields --expected-host HOST
--expected-database DATABASE` in the configured SAMPLE PostgreSQL environment.
Inspect the dry-run, then repeat with `--apply --expected-revision REVISION`.
Apply requires the current schema and reviewed revision. Replay creates no new
versions. Omission cannot delete rows; account reassignment is rejected. Corrected
fields append a version and preserve prior evidence. A compatible code rollback
retains these tables; destructive downgrade is deliberately unavailable.

Authenticated account and map disclosures load bounded pages from
`/api/accounts/{id}/workbook-fields`. Immutable versions are scoped again by
account at `.../workbook-fields/{version_id}`. The existing application principal
boundary and private/no-store responses apply; this does not invent multi-tenancy.
The interface retains the current disclosure page on collapse, cancels stale
requests, and resets when account scope changes. Full-navigation draft/scroll
retention is a separate qualification requirement, not established by these tests.
