# Saved communication versions

Migration 0031 adds a monotonic version to the existing draft owner. Legacy drafts
start at version 1 without reconstructing fictional historical versions. Every
content edit or review uses an atomic SQL compare-and-swap and increments the
version. The audit event commits with the change; a stale or concurrent loser
creates neither a replacement draft nor a successful audit event.

API edits, reviews, saved-draft assistance and send requests require the version
the caller reviewed. Edits invalidate approval. Closed/sent drafts cannot be
reviewed back into a sendable state. Assistance checks the version before and
after synthesis; it returns a proposal, not a saved change. Client inputs remain
unchanged after a rejected save. Refresh displays the saved content/recipient/
approval alongside local text. Explicitly accepting that version only changes
the next save precondition; it does not submit or approve anything.

Delivery previews and failed-provider receipts append audit only. They never
write back the full draft they read. A concurrent draft update invalidates a
preview rather than reverting current content. Read operations require existing
scope permissions but no new approval. Creation replay remains actor-scoped and
returns the current saved record, without reverting later edits.

External delivery remains the existing unconfigured adapter. Tests use isolated
recording adapters only, never researched real recipients. These version guards
do not qualify an external delivery integration: a future real send still needs
durable pre-call attempts, destination authority and provider idempotency/outcome
reconciliation. No message was sent by this implementation or its qualification.
