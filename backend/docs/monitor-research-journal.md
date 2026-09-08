# Monitor public investigation journal

`monitor/worker.py` invokes `MonitorResearchCoordinator` within the existing Monitor worker and its operational lock. No second monitor, queue service or model dependency is introduced. `monitor/repository.py` owns public research runs/steps through `MonitorResearchJournal`; schema0033 is additive.

The coordinator uses the configured existing Gemini provider. Hosting and API mode remain configuration, not a claim of BTX Google Cloud deployment. The external scheduler invokes the existing worker; creating this journal does not prove a scheduled or hosted execution.

Bounds: at most2 investigations per worker by default (`BTX_MONITOR_RESEARCH_CAP`,0–3);4 public tools,12 journal steps,3 persisted attempts,90-second worker investigation slice and the overall worker deadline. Paused attempts wait60 then120 seconds; completed same-source/configuration/date research reuses its persisted result. Configuration version is `BTX_MONITOR_RESEARCH_COORDINATOR_2`. The date partitions current research; it does not relabel source publication dates as fresh.

Tool selection is model-driven but closed to public document fetch and server-built public searches. The model cannot supply an arbitrary fetch URL, private query, canonical identity approval, deterministic score, commercial transaction, message or CRM write. Search snippets are discovery leads, not extracted article evidence. Source passages carry checksum, URL, retrieval date and explicit extraction completeness; unknown publication/event dates remain unknown.

Version2 supplies remaining source/focus values as schema enums while retaining independent server validation. All retained article passages enter subsequent selection context (18,000-character extraction cap per document, at most4 public tools), avoiding unnecessary searches caused by hiding later paragraphs. Existing Gemini3 low-thinking configuration also applies to grounded searches within the unchanged output budget. Prior version failures remain audited, not rewritten.

Current public reads use the repository's committed event/observation snapshot, so a separate worker's updates do not require restarting the API. Evidence inspection, technical decomposition and selected-event Omni retrieval share the same exact source-revision research join. Partial research remains labeled partial; source corrections cannot reuse an earlier assertion's research. The UI exposes run metadata inside its existing evidence disclosure, with authenticated private/no-store API responses.

Every call is admitted in a short transaction before network work. A token/expiry fences late responses after another worker resumes. An interrupted call remains `INTERRUPTED_UNKNOWN`; completed steps are immutable and acknowledgement replay is idempotent. PostgreSQL transactions have2-second lock/5-second statement limits. Public result sizes are bounded; private seller prompts and chain-of-thought do not belong in this journal.

`RESEARCH_RECORDED` means retrieved research persisted, **not publication or a qualified prospect**. Results explicitly require existing canonicalization, relevance, score and publication gates. Until the downstream integration and fresh live/scheduled/hosted checks pass, this unit alone does not complete the research release requirement.

Qualification: `tests/test_monitor_research_journal.py` runs lease/replay/cooldown/immutability/concurrent-admission tests in SQLite and a uniquely named disposable PostgreSQL schema. It refuses non-loopback or non-qualification database targets. `tests/test_monitor_research_coordinator.py` exercises the actual coordinator/extractor with explicitly injected test providers, not live-Gemini evidence.
