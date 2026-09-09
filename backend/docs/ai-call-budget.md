# Durable AI call budget — BTX_AI_CALL_BUDGET_1

The existing Gemini provider reserves each SDK call in `ai_call_receipts`, including
Google Search grounding. Reservation commits before network access. No table or
advisory lock spans a provider call. Missing/unavailable accounting fails closed.
Actor IDs come from authenticated server principals; background Monitor calls use
`system:monitor`. The existing database is the workspace boundary, not invented
cross-tenant authorization. Every request still uses existing permissions.

Provisional SAMPLE defaults: 1,000 calls per workspace UTC day, 400 per actor,
two concurrent workspace leases and one per actor. Settings are
`BTX_AI_DAILY_ENVIRONMENT_CALLS`, `BTX_AI_DAILY_ACTOR_CALLS`,
`BTX_AI_CONCURRENT_ENVIRONMENT_CALLS`, `BTX_AI_CONCURRENT_ACTOR_CALLS`.
These bounded starting values allow multi-step POC evaluation while stopping
runaway repeated requests; they are not measured throughput or provider quotas.
An invalid relative limit fails closed. Failed calls consume their reservation.
The SDK timeout is bounded to 120 seconds. Leases last timeout plus 30 seconds
(at least 30); an abandoned lease becomes an unknown outcome, not a refund.
Lease concurrency is not proof that a disconnected provider has stopped work.

Receipts contain model, purpose, timestamps, policy, status and available token
counts. They contain no prompts, answers, secret keys or private reasoning.
`RESPONSE_RECEIVED` describes transport, not correct synthesis or task completion.
Completed receipts cannot be changed. A late result may complete an expired
unknown reservation. If recording completion fails, the call remains counted and
the response fails safely. Retries reserve another call; no automatic refunds.

Settings exposes the caller's aggregate usage plus workspace call totals, never
another user's identity or prompts. Private responses are not cacheable. Known
token sums explicitly exclude unknown usage. Cost is null: no estimated price is
presented as billed spend. There is no new paid dependency, model-based formula,
external CRM write or deployment permission change.

Migration 0030 is additive. Retain receipt history during compatible code rollback;
destructive downgrade is intentionally rejected. Qualify on disposable PostgreSQL
before applying to the designated SAMPLE deployment.
