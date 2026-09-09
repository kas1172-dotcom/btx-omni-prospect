# Release identity gate

`GET /api/health` is liveness only. Public `GET /api/build` contains validated code identifiers, never database destinations, accounts or credentials. Authenticated `/api/settings` checks the exact required Alembic head with bounded SQL timeouts and real UTC check time. It does not run provider calls or claim browser acceptance.

The frontend publishes `/build.json` and embeds the same metadata in its bundle. Vite checks the actual origin and any supplied Vercel commit/repository metadata, refusing mismatches. Dirty or unavailable Git checkouts stay unverified; no environment secrets are serialized. Settings compares the frontend and backend declarations, explicitly reporting mismatches.

For a release, use an independently reviewed clean checkout of the merged commit. Record `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` and supply those public values as Fly build arguments `BTX_RELEASE_SHA`, `BTX_RELEASE_TREE`, plus `BTX_RELEASE_WORKTREE=clean`. Do not set clean for a modified checkout. Confirm these values in the deployed image configuration and `/api/build`; do not rely on a mutable runtime override as evidence. Existing Docker defaults deliberately remain unknown.

Build the linked Vercel frontend from that same commit. Compare both public build responses with the recorded merged SHA/tree and hosting deployment IDs. Missing Git metadata is an unresolved identity gate, not permission to fabricate a tree. Check actual database revision through authenticated Settings and compare with `required_revision`. Source build metadata is not a substitute for backup/restore, enriched import/replay, real Maps/Gemini, scheduled execution or hosted seller journeys. Keep these separate release gates.
