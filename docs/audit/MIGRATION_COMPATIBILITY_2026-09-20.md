# Actions / Network / Chat migration compatibility

This branch joins the existing Actions and Network/Chat migration histories without renaming applied revisions. It is a migration integration candidate, not a merge of the feature implementations.

Shared head: `0042_merge_actions_network_chat`.
Parents: `0039_actions_pm_workspace` and `0041_omni_conversations`.

Validation on 2026-09-20:
- Six migration tests passed, including fresh SQLite and upgrades from both feature heads.
- Fresh PostgreSQL and both existing feature heads upgraded successfully in three dedicated local databases.
- Both feature schemas, approval columns, and a retained fixture row survived each upgrade.
- No production database was touched. Actions' existing restriction on destructive downgrade remains in place.

Raw PostgreSQL verification: `C:/Users/Aruna/AppData/Local/Temp/btx-migration-postgres.log`.
