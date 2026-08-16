# Monitor historical benchmark plan

Create an initial verified corpus of **at least 100 events**, balanced across the six Phase 1 industries (minimum 16 each, then allocate the remaining four to underrepresented event classes). Do not add an event until its primary evidence is saved as a stable official or authoritative reference.

Benchmark row schema: `benchmark_id`, `industry_pack`, `expected_event_type`, `event_date`, `subject_account_id?`, `subject_legal_name`, `program_id?`, `geography?`, `amount/currency?`, `primary_source_system`, `source_record_id?`, `evidence_url`, `evidence_captured_at`, `verified_by`, `verification_notes`, `expected_resolution_state`, `negative_case?`.

Population process: select event classes from the ontology; locate official/authoritative records; verify date/entity/type against the reference; capture immutable excerpt/hash; resolve to governed accounts only when justified; dual-review disputed labels; freeze versioned benchmark releases before measuring. Never synthesize events from press summaries.

Report recall, precision, entity-resolution accuracy, event-type accuracy, duplicate rate, detection latency and source coverage by source and industry pack. Hold out a portion by time and source.

Required negative cases: same-name entity collision; reposted old event; contract modification mistaken for new award; cancelled solicitation; rumor/unsupported claim; incorrect parent/subsidiary mapping; irrelevant regulatory event; irrelevant geographic expansion. Rejections retain lightweight observation/evidence context and a traceable rejection state.
