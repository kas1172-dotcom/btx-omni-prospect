# Phase 19 — Actions + Omni

Actions are durable internal Omni work items. A seller explicitly creates an Action against a canonical Customer or Prospect, then may set its owner, priority, due date, evidence IDs, and bounded typed context referents (for example Intelligence, Federal Procurement, relationship, or facility IDs). The supported lifecycle is `OPEN` → `IN_PROGRESS` → `COMPLETED` (or cancellation); manager approval remains available only for workflows that require it. History records actor, time, and change metadata. Updates use an Action version so a stale edit returns a conflict rather than overwriting a newer update.

Actions do not create HubSpot tasks, mutate a deal, send email, or perform any external write. Existing external preview/execute seams remain separately governed and explicitly disclosed as simulated where applicable.

Omni is a read-oriented assistant over authoritative bounded projections. Its referents are typed canonical IDs for Customers/Prospects, Intelligence, Federal Procurement, relationships, facilities, and Actions. It preserves referent continuity, asks for clarification when target identity is ambiguous, and distinguishes evidence, missing data, SAMPLE commercial context, and configured-provider state. Gemini can improve phrasing only; deterministic governed fallback remains usable when it is not configured or unavailable.

Omni may recommend an Action, but never creates one autonomously. The seller must enter the normal Actions workflow, review the form, and explicitly save. Known limitation: contextual referents are durable IDs and are rendered as compact identifiers until each source surface supplies a richer display projection.
