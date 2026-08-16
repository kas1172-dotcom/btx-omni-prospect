# Monitor 2.0 target architecture

Monitor answers **“What happened?”** It owns proactive, scheduled collection from a known source universe and creation of canonical, evidence-linked Intelligence. It does not own Account Attractiveness, commercial prioritization, quote correlation, CRM decisioning, seller Actions, or Omni recommendations.

```text
Sources → source adapters → raw evidence/reference → normalization
→ canonical IntelligenceEvent → entity/program resolution → dedupe/event clustering
→ Commercial Matching → scoring/Commercial Alerts → Today / Intelligence / Map
→ Omni → human-approved Action
```

Adapters preserve a stable source identity, source-native record identifier, version/hash, immutable evidence locator and collection timestamps. Normalization creates explicit claims rather than a source-shaped record. Entity and program resolution never silently creates an account: unresolved and ambiguous cases remain reviewable. Clustering converts many observations into one event with many evidence records; changed records create a new source version and may update or supersede an event.

Stage A is a high-recall, low-cost plausibility filter: watched account/alias, program, Phase 1 industry, enabled event class, sourcing/manufacturing context, geography and known capability category. Stage B is the existing governed Omni Prospect Commercial Matching boundary. Monitor emits no attractiveness score and no seller recommendation.

Monitor and Omni research are intentionally distinct. Monitor is proactive, scheduled and source-universe driven; its accepted output becomes canonical Intelligence. Omni research is reactive and user-requested, requires public provenance, and remains research material unless an explicit governed intake promotes it into Monitor intelligence.

No persistence migration is included in this checkpoint. The foundation contracts define a future persistence boundary without duplicating current canonical Intelligence, Evidence, Account, Program, Matching, alert, Omni or Action domain records.

Checkpoint 12 adds narrow Monitor operational persistence: source observations hold source record/version/hash, canonical URL and a payload reference (not source-specific columns); collection runs, health state, and cluster membership are persisted separately. Canonical account, Intelligence, Evidence and commercial tables remain source-neutral.

## Deduplication, lifecycle and audit

Every observation has `source_record_id`, `SourceVersion.version_id`, `content_hash`, `first_seen_at`, `last_seen_at`, and optional `changed_at`. The source-record key recognizes the same record; the hash recognizes changed content. Event clustering uses event type, resolved subject (or normalized unresolved mention), program and event-date window to propose a cluster, then retains every observation and evidence record. A source update can revise an event; a materially changed fact can supersede it through `supersedes_event_id`. Related events and `InitiativeLink` express a multi-event initiative lifecycle without collapsing distinct events. Ambiguity is first-class and blocks automatic resolution.

Rejected observations retain observation ID, evidence ID, reason, timestamp and one of: `NOT_RELEVANT`, `NO_ENTITY_MATCH`, `AMBIGUOUS_ENTITY`, `DUPLICATE_EVENT`, `EXPIRED_EVENT`, `UNSUPPORTED_CLAIM`, `INSUFFICIENT_EVIDENCE`, `OUTSIDE_PHASE_1_SCOPE`.

## Collection state and health

`CollectionRun` records `last_attempt`, `last_success`, cursor/page/token, records seen/new/changed/rejected, events created/matched, failures and latency. `SourceHealth` independently records health state and emits `SOURCE_HEALTH_WARNING` on stalled, failed, degraded or suspiciously empty collection. It is operational observability, never a Commercial Alert; source failure means unknown coverage, not no events.

## Industry packs

The generic core receives configuration-only packs: `commercial_aerospace`, `defense`, `space`, `semiconductor`, `medical_device`, and `robotics`. Each declares enabled event types, adapter/source configuration, watched target entities, relevant agencies, terminology, program vocabulary, geography rules, industry filters, source-native identifier kinds and confidence rules. The core contains no customer/company-specific strings or score thresholds.
