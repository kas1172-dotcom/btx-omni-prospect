# Monitor 2.0 Phase 1 live sources

`MONITOR_MODE=disabled` is the default and performs no network collection. `MONITOR_MODE=live` permits explicit source collection only; it never substitutes sample records. `SAM_API_KEY` is required for SAM.gov. USAspending, Federal Register, SEC EDGAR, openFDA, NASA, DoD, Commerce, verified official company feeds, and state/local official publishers are keyless, subject to their published access rules.

The registry declares authority tier, supported industries/events, cadence, backfill, authentication, rate-limit notes, endpoint and source-native identity strategy for SAM.gov, USAspending, Federal Register, SEC EDGAR, NASA, DoD, Commerce CHIPS, FDA/openFDA, company newsrooms and state economic development sources. Publisher/watch-profile sources require a verified canonical URL; a missing URL is a missing-data state, never a guessed feed.

Structured APIs are deterministically mapped before any AI path. The provider-neutral AI contract supports extraction, classification, ambiguity resolution, summarization and entity assistance. `AI_PROVIDER=anthropic` selects the initial adapter, with `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`; its results always retain evidence IDs and require validation. No AI output is canonical truth by itself.
