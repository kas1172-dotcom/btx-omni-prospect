# Monitor 2.0 — old Monitor audit

## Verdict

The donor is useful research material but is not a migration target. Its `monitor_engine` is a client-configured feed collector plus keyword/LLM analysis and generated-artifact workflow. It mixes discovery, relevance, client fit, narrative output, and deployment artifacts; Monitor 2.0 must instead create traceable canonical intelligence for Omni Prospect.

| Donor component | Finding | Decision |
| --- | --- | --- |
| RSS, JSON API, HTML-list collectors | Generic HTTP retrieval and source isolation are sound concepts; selectors and field maps are brittle source implementation details. | REIMPLEMENT |
| `RawItem`, source config schemas | Carries title, URL, date and source, but lacks record versioning, evidence lineage, canonical events, resolution and source-native identities. | REPLACE |
| Parser/date helpers | Deterministic parsing and explicit unknown-date handling are useful. | REIMPLEMENT |
| Keyword prefilter / vertical scopes | Client terms and static include/exclude filtering are too weak as the system boundary. | REPLACE |
| LLM scorer, tiers, prompts, deep analysis | Produces BTX “why it matters/now what” prioritization, not fact acquisition; opaque confidence and client capability context leak into Monitor. | DELETE |
| Enrichment connectors | The adapter concept is useful, but opportunistic API enrichment during analysis is not evidence-first collection. | REIMPLEMENT |
| Archive JSON / hash dedupe | A content archive is a useful concept, but JSON-file state cannot express update, event, and evidence lifecycle. | REIMPLEMENT |
| Grouping | Topic grouping is not canonical event clustering or initiative lifecycle. | REPLACE |
| Target/account-map sources and fit scoring | Market targeting and BTX-fit scoring are outside “what happened?”. | DELETE |
| Client config (`clients/btx`) | BTX brand, capability, geography, scoring, named entities and output editions are tenant assumptions. | DELETE |
| Scheduling/cadence | Cron configuration is a useful external orchestration concept; no durable per-source cursor/run state exists. | REIMPLEMENT |
| Source health | Explicit zero/error outcomes are worth retaining, but health must be durable and separate from commercial alerts. | REIMPLEMENT |
| Generated `run_output`, map and frontend artifacts | Presentation artifacts are not Monitor’s canonical output. | DELETE |
| Tests | Collector/parser/health fixtures provide useful test patterns; tests assert old artifact and LLM workflow. | REIMPLEMENT |
| GitHub Actions refresh workflow | Manual live collection with secrets, LLM calls, artifact commits and deploy is unsuitable for this foundation. CI test gate is a useful concept. | REPLACE |

The old implementation uses RSS/JSON/HTML collectors, Pydantic config, feed-level dedupe/archive, cron config, optional API enrichers, LLM scoring/research, source-health summaries, JSON output, and manual GitHub Actions refresh. It has no source-version model, canonical event/evidence graph, resolution ambiguity contract, durable collection cursor, or clean downstream commercial boundary.
