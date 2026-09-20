# Integrated sample demo release — 2026-09-20

Combines Omni chat, LinkedIn relationship ingestion, Actions and migration compatibility, Profiles, Communications, Map, Today, Opportunities and sample journey enhancements. The Monitor fix branch is excluded.

Integration repairs retain the new Actions editor for Omni proposals, customer source links, bounded decision drilldown, the new Map controls, and profiles without a commercial ledger. New Actions use the demo business clock. Network privacy inventory covers the combined routes.

Validation: 1,099 backend tests passed; 130 frontend unit tests passed; lint, TypeScript and production build passed. Twenty desktop/mobile screen smoke checks passed. Thirty selected workflow tests were exercised: 26 initially passed; all four initial failures were resolved and rerun successfully (customer source link, itinerary locator, baseline empty Opportunities, and enhanced relationship fixture). The relationship test uses E2E_RELATIONSHIP_ACCOUNT=demo-regional-defense for enhanced fixtures; the empty Opportunities case runs against an unenhanced baseline. Enhanced regional cards/graph and fictional Watch profile also passed separate browser checks. Baseline Boeing missing-ledger rendering was checked after repair.

Deployment enables deterministic SAMPLE enhancement anchored at 2026-09-20. Live Monitor collection and durable monitor/commercial imports are disabled for this demo. Existing hosted authentication and secret-managed integrations remain in place. The live database's prior migration marker and existing work/audit tables were copied into release_backup_20260920 before migration. No recognized new secret patterns were found in the release diff.

Demo entry points: Today, Boeing recovery (292 ordered / 146 shipped / 146 open), Fictional Watch Manufacturing, regional defense relationship routes, and Map regional planning. Synthetic records are labeled; unknown evidence and hypothetical relationships remain explicit. Local browser checks used the map test provider; live Gemini and Google Maps require post-deployment checks.
