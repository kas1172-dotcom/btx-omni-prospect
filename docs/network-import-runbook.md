# Local network import runbook

This release is a **fake-data-only local verification build**, not authorization to use a real export. The final audit's NEEDS HUMAN items must be resolved before that restriction can change. Never run these commands against a hosted database. Never put input data, screenshots, or generated reports in any git worktree.

## Prepare a local environment

Use a task-owned PostgreSQL database bound to `127.0.0.1`. Set `BTX_DATABASE_URL` explicitly; do not copy a production `.env`. Network CLI commands reject non-loopback PostgreSQL URLs, including host/service query overrides. Do not use an SSH tunnel or proxy to make a remote database appear local.

Run migrations only after independently checking the database host and ownership. `alembic upgrade head` applies the network tables. For disposable verification, `alembic downgrade 0038_federal_opportunity_pipeline` removes the network tables, then `alembic upgrade head` restores them. Migration 0038 intentionally blocks a full downgrade to base; do not change that safeguard.

Set `OMNI_TENANT_ID` on the server. It is the sole tenant authority for Principal, not a request parameter, cookie, user ID, or header. For real identity isolation, configure `BTX_USER_ACCESS_CODE_HASHES` as a server-side JSON object mapping unique stable user IDs to lowercase SHA-256 hashes of high-entropy random access codes. Never use human passwords as these codes; never log the map or raw codes. All mapped users receive the existing salesperson role (least privilege). Duplicate hashes and reserved `shared-access*` identities are refused. Ambiguous codes matching both a user and a legacy code fail closed.

Legacy shared salesperson/demo sessions use `shared-access`; shared manager sessions use `shared-access-manager`. Neither can own, import, share, or view owner-only batches. They may view explicitly tenant-shared data if the tenant and existing CRM role permit it. Distinct role IDs preserve existing private-memory separation. There is no identity provider yet, and sessions are in memory; restart revokes them. Removing a configured code does not revoke already-issued sessions: restart the local server when changing access authority.

For fake UI inspection only, development mode uses the existing `seller-1` principal. Never use that fallback for real files. Hosted configuration sets `BTX_ENVIRONMENT=production`; `api/session.py` permits development-token fallback only when the value equals `development`.

## Dry-run, review, import

Run from `backend`, with its Python environment active. Keep the fake CSV outside all worktrees. Supply a timezone-aware export date (the file's export date, not a connection date):

```powershell
python -m btx_omni.persistence.network_import import-linkedin C:/local-fake-drop/Connections.csv --tenant-id fake-local --owner-user-id fake-user-1 --owner-name "Fake Owner" --exported-at 2026-09-20T00:00:00+00:00
# Review masked counts first. Only then repeat with --apply.
```

Dry-run makes no writes. Writes require `--apply`. CLI import output omits personal fields, batch IDs, and file hashes. The database retains batch IDs/hashes for audit. Obtain a batch ID with a read-only local SQL query selecting only `id`, `exported_at`, `status`, and row counts from `network_import_batches`, constrained to the intended tenant and owner; do not select personal columns.

```powershell
python -m btx_omni.persistence.network_import report-unresolved --tenant-id fake-local
```

The report emits JSON lines with company strings and contact counts only, ranked by count. It is not a CSV export; formula-leading values are nevertheless prefixed with an apostrophe for spreadsheet safety. Counts reflect active snapshots only. Review unknown or ambiguous organizations; this command never creates accounts. Empty company strings remain unresolved, not invented companies. Company strings themselves require review before sharing reports because a sole-trader company name could be personal data.

The official Connections.csv adapter accepts UTF-8 BOM, CRLF, up to 100 preamble lines, blank titles and companies, non-ASCII names, and supported connected dates (`04 Mar 2024`, ISO date, US slash date). Blank/unparseable connected dates become null. Blank names are skipped; exact duplicate normalized records collapse. Fields over their schema limits and files over 10 MiB are rejected without printing input. No fuzzy matching or account creation occurs; resolution uses existing read-only governed exact/normalized matching. Unknown titles become unclassified.

An identical file is idempotent within tenant/source and cannot be reassigned to another owner. A different file must have a strictly newer export date than that owner's active snapshot. It supersedes the old batch atomically, starts owner-only, and does not inherit sharing. Superseded rows remain stored for audit and explicit purge, but are excluded from views and unresolved counts. Purging a newer batch does not reactivate older snapshots. Do not run concurrent imports for the same owner; serialized operational imports are required.

## Share explicitly

Sharing is a separate local operator action through `share_batch`, never an import default:

```powershell
python -m btx_omni.persistence.network_import share-batch BATCH_ID --tenant-id fake-local --owner-user-id fake-user-1
python -m btx_omni.persistence.network_import share-batch BATCH_ID --tenant-id fake-local --owner-user-id fake-user-1 --apply --confirm BATCH_ID
```

The CLI is an operator tool, not an authentication boundary: access to the local database and shell must be restricted. The owner argument must agree with the stored owner. Visibility always requires matching server tenant and an existing CRM-readable role.

## Purge

```powershell
python -m btx_omni.persistence.network_import purge BATCH_ID --tenant-id fake-local
python -m btx_omni.persistence.network_import purge BATCH_ID --tenant-id fake-local --apply --confirm BATCH_ID
```

Type the exact batch ID as confirmation. The write is a hard delete in one locked transaction: affiliations, ties, unresolved review rows, people, then batch. Output contains status and masked counts only. Repeating a purge returns zero counts/NOT_FOUND. A wrong tenant also returns zero counts. There is no imported-row process cache; refresh or close already-open browser views after purge. Purge does not erase external backups, database WAL, or screenshots; those require the local retention policy.

## Stored and excluded data

Stored: tenant/source/file hash/export and import timestamps, unique owner ID, owner name, batch status/visibility/counts; external display name/profile URL; raw company/title, account match/method/state, derived role family/seniority/export date; connection date and provenance. Rows are IMPORTED, asserted/needs-validation and weak. A LinkedIn connection is never a documented introduction.

Never stored by this importer: email or phone columns. Never sent to model prompts/logs: imported names, profile URLs, or raw titles. Only allowlisted aggregates and generic unvalidated provenance may enter model context. Imported identities are read only by relationship query and the explicit account commercial contact list; not Today, map, directory, briefing, or Omni retrieval. Existing rubric weights, versions, outputs, node sizes, and the monitor resolver are unchanged by this task. Account-level role targeting remains coarse; it does not establish a validated warm introduction or person-level buying authority.

## Fake seed

```powershell
python -m btx_omni.persistence.seed_network_sample --tenant-id fake-local --owner-user-id seller-1
python -m btx_omni.persistence.seed_network_sample --tenant-id fake-local --owner-user-id seller-1 --apply
```

Requires pre-existing canonical local accounts. Creates 200 explicitly fake contacts through temporary CSV outside the repo, source `local_fake_network_seed`, then deletes the temporary file. It exercises the IMPORTED storage contract; it is not production or SAMPLE-view data.

## Before any real file: all must be true

- A human explicitly lifts this task's fake-data-only limit after reviewing the final audit. Until then: NO-GO.
- All privacy/prompt/cache/browser gates pass; unresolved NEEDS HUMAN items have documented dispositions.
- Database is owned, local, encrypted as appropriate, not tunneled, not syncing to cloud backups; logs and screenshots are disabled or appropriately protected.
- Server runs production authentication mode on loopback, demo bypass disabled, unique per-user code hashes configured, correct server tenant, no shared or development owner.
- Source owner's authorization, retention period, and deletion process are recorded outside git; raw files stay outside worktrees and cloud-sync folders.
- Preview counts and unresolved company report are reviewed without personal-field output; no new accounts are created automatically.
- Understand no IdP, in-memory session/revocation limits, serialized imports, account-level targeting, unvalidated relationships, and snapshots retained until purged.
- Batch remains owner-only unless separate explicit sharing is authorized; tested purge command and local backup/WAL retention are understood.
