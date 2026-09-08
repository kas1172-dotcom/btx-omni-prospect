# Private Omni preference operations

Memory is explicitly authored per-user style/work preference, optionally account scoped, not evidence or authorization. Existing `/api/omni/memories` CRUD requires the normal principal and hosted CSRF checks. Managers cannot read or edit other users' preferences. Expiry is measured against real UTC, not the commercial demo clock.

Creation requires an 8–64 character `idempotency_key`. The frontend reuses it after an uncertain response while the same draft remains active. Identical replay returns current saved state without reapplying content or extending expiry. A conflicting payload gets 409; edits use `expected_version`. Refresh and inspect after an interrupted edit rather than guessing its outcome.

Migration `0027_memory_create_receipts` adds a minimal per-user request receipt (hashed key/payload, memory ID and time). No preference text or response snapshot is retained in receipts. Deletion removes active preference content; a prior create request cannot resurrect it. Earlier conversation responses/backups are not rewritten. Per-user transaction locks serialize create/delete and enforce 25 stored preferences / 1,000 create receipts in this bounded POC. Exhausted receipt capacity requires operator review, not silently deleting replay protection.

The same-draft retry key is held in the current component, not private browser storage. A full browser reload discards an unsaved draft; inspect stored preferences before authoring a new one. This limitation remains visible in qualification and is not an assertion that all workspace drafts persist across navigation.
