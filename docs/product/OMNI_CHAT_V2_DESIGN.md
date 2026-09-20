# Omni chat v2 design

Starting revision: `68cb63379f68e5a8c723a300642bad004152f725`. Starting checkout clean.
Implementation lives in the separate `btx-omni-chat-v2` worktree on `codex/omni-chat-v2`.

## Authority and scope

Chat is available to authenticated BTX users. Business data remains read-only.
Only private conversation, feedback and audit records may be written. Action proposals
open the existing reviewed creation form. No scoring, CRM or Action mutation service changes.
The scoring working draft in `docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`
was inspected. Its prospective probability language and historical weighting descriptions
do not override the mission: PWIN is an index and current deterministic services own scores.
No Project Scope document was found under docs.

## Existing owners to reuse

- `backend/src/btx_omni/modules/commercial/read.py`: CommercialReadService.account_snapshot and quote_comparison.
- `backend/src/btx_omni/modules/commercial/lifecycle.py`: fulfillment_state.
- `backend/src/btx_omni/modules/assistant/commercial_tools.py`: CommercialToolSession.read.
- `backend/src/btx_omni/modules/accounts/customer_360.py`: organization_360_projection and customer_360_projection.
- `backend/src/btx_omni/modules/scoring/commercial_decisions.py`: customer_decisions (including eligibility, factors, coverage and versions).
- `backend/src/btx_omni/modules/commercial/opportunities.py`: selected_opportunity and account_opportunities.
- `backend/src/btx_omni/modules/relationships/service.py`: RelationshipIntelligenceService.
- `backend/src/btx_omni/modules/assistant/relationship_context.py`: selected_relationship_context.
- `backend/src/btx_omni/api/map.py`: haversine_miles; straight-line distance only.
- `backend/src/btx_omni/modules/alerts/commercial.py`: CommercialAlertEngine.evaluate.
- `backend/src/btx_omni/modules/federal_procurement.py`: procurement_projection.
- `backend/src/btx_omni/api/intelligence_projection.py`: intelligence_signals.
- `backend/src/btx_omni/modules/work/service.py`: WorkService.list(current).
- `backend/src/btx_omni/ai/gemini.py`: metered Gemini generation and Google Search grounding.
- `backend/src/btx_omni/persistence/omni_runs.py`: private immutable answer receipts.

## Tool contracts

Every input is a JSON object with additionalProperties=false. Strings are bounded;
lists are capped, scopes come from the server principal, and results have a size cap.
Common output: `{status, as_of, source_ids: string[], data_mode, data: object}`.
Dates are ISO dates, money is projected by existing money helpers, and absent data is explicit.

| Tool | Input properties | Data output |
| --- | --- | --- |
| find_organization | name: string (1..160) | status matched/candidates/not_found, confidence, at most three {id,name} candidates |
| get_customer_360 | account_id: string | organization, identity and existing 360 projection |
| get_commercial_history | account_id: string, quote_id?: string | quote/order rows, revisions, fulfillment, backlog, totals and dates |
| get_intelligence_events | account_id?: string | at most ten visible events, source URLs |
| get_assessments | account_id: string | distinct score families, factors, coverage, gaps, eligibility, rule versions |
| get_relationship_routes | account_id: string | bounded source-backed routes, constraints, access limitations |
| get_nearby_sites | account_id: string | verified locations and straight-line miles; no travel times |
| get_actions | account_id?: string | at most ten principal-visible Actions |
| get_today_priorities | account_id?: string | deterministic alerts and visible work |
| get_federal_opportunities | account_id?: string | existing federal projection or explicit unavailable state |
| compare_organizations | account_ids: string[2] | two independent organization/history summaries; no new score |
| get_screen_context | empty object | validated selected entities, visible IDs and bounded filters |
| web_search | topic: enum, account_id?: string | public-only query; title, publisher, URL, publication date or unknown, retrieved date, findings |

Input/output schemas will also be executable in the tool module. A tool cannot take
an arbitrary SQL query, URL, owner, actor, tenant, or credential. Search topics are
allowlisted public concepts; internal question text is never sent to Google Search.

## Agent and provider

The configured model chooses tools and final language through a bounded JSON protocol.
Default six tool steps; bounded input/output tokens; per-tool and request deadlines;
existing actor/environment metering plus chat daily cap. Invalid model selections fail
closed. Recent turns are linguistic context, never evidence. Named entities precede
passive screen scope. Unknown explicit names return not-found, never market cohorts.
Comparisons may use exactly the two explicitly named/resolved organizations.

The old OmniService/OmniOrchestrator remain compatibility and degraded read internals.
They are not the normal model planner. No old routing is deleted before golden evaluation.
Missing Gemini is a supported state: a plain disclosure followed by basic safe lookups.

## Validation and presentation

Model output is untrusted. Validate facts, numbers, dates, entities, URLs, sample labels,
score family/version/coverage and completed-write claims. Retry once with a violation;
then build plain fallback from tool data. Public findings never enter canonical storage.
Public and internal facts are separate for mixed answers. General knowledge is labeled
by provenance and must not borrow authority from BTX data. No invented contacts/access.

SSE emits progress then validated answer text; never stream unvalidated model content.
Disconnect/cancel halts subsequent work (an in-flight SDK request is timeout bounded).
Safe Markdown supports paragraphs, lists, bold and safe links only. Technical details
are collapsed. Conversation list/resume/rename/delete and feedback are actor-scoped.
Retention is configurable; deletion removes conversation content and feedback.

## Tenant finding and risks

Principal.tenant_id now exists, supplied by server Settings via security/sessions.py.
The existing commercial catalog is still a single workspace; core account tables are
not tenant partitioned. Do not claim multi-tenant business-data isolation. Chat must
reuse existing role visibility and scope private storage by actor plus tenant.
Hosted POC identity currently maps access codes to shared seller/manager identities;
corporate individual identity is an external prerequisite for personal production history.

Risks: heuristic names cannot prove arbitrary semantic grounding; public search metadata
may lack publication dates; source snippets may contain injection; strict validation
may reduce fluent answers; existing browser tests encode legacy text/transport. Tests
will be updated only for intentional behavior changes, with reasons recorded here.

## Gates and evaluation

M0 path/design validation; M1 fake tools/agent plus backend; M2 search privacy/general;
M3 validation/degradation; M4 persistence migration and frontend gates; M5 documentation;
M6 at least 60 behavioral cases, fake provider in normal CI and optional live report.
Tests use task-owned databases. No deployment or production writes.
Final results, baseline differences and limitations belong in OMNI_CHAT_V2_REPORT.md.

### Baseline repairs and compatibility

The first PostgreSQL baseline was 752 passed / 55 failed. Most failures came from
Git's Windows CRLF checkout conversion breaking byte-hashed research fixtures.
Only unchanged fixture files were normalized back to their committed LF bytes;
no fixture content or reviewed hash was changed. The first SQLite-only trial was
not a valid full-suite baseline because PostgreSQL journal tests require PostgreSQL.

Two legacy Omni acceptance assertions predated existing human-readable alert labels
and opportunity-scoped ranking. They now assert plain labels and explicitly missing
opportunity inputs; scoring behavior is unchanged. A Monitor persistence test now
checks the failed run by ID, preserving its failure-persistence assertion without
assuming distinct Windows timestamps. No tests are skipped or removed.
The monitor heartbeat test now waits for its observed heartbeat event (up to two
seconds) instead of assuming the Windows scheduler starts a thread within 10 ms.
Six baseline Ruff findings were repaired with import formatting and a dictionary
literal; these do not change network or migration behavior.

The additive `/api/omni/chat` endpoint is the v2 entry point. `/api/omni` remains
available for existing integrations and compatibility tests. The UI switches to v2
in M4. Neither endpoint gains business writes.

### Public search decision

`chat_web.py` deliberately accepts a closed topic enum and canonical public company
name only. No user/model free-form query, internal program label, commercial number,
contact, note or score can enter the grounding request. This limits arbitrary-topic
fresh research; extending it requires a reviewed public vocabulary, not a raw-query
escape hatch. Publication dates remain unknown when grounding omits them; retrieval
dates are separately labeled. Search excerpts are untrusted, with known instruction
patterns withheld, never persisted as canonical evidence or scoring inputs.
`WEB_SEARCH_ENABLED` and `GENERAL_KNOWLEDGE_ENABLED` default true; search additionally
requires a configured provider. Explicitly disabling either is enforced in code.

### Validation and limits implementation

`chat_prompt.py` is the v2 system prompt; existing legacy prompts remain for the
compatibility endpoint. `chat_validation.py` checks lexical numbers, capitalized
entities, source URLs, public paragraph citations, completed writes, sample labels,
PWIN wording and assessment version/coverage. One correction attempt is allowed.
These checks are conservative heuristics, NOT a proof that every natural-language
claim follows from evidence; lowercase invented names and semantic inversions remain
limitations requiring live adversarial evaluation. Two stable general facts (France's
capital and NAICS 3364) have explicit local factual context; other new named/numeric
general facts may fail closed pending a sourced lookup rather than bypass validation.
This deliberately favors admitting uncertainty over fluent unsupported answers.

Each model response is token-bounded; the request has at most steps+2 model calls,
so the configured output-token ceiling times steps+2 is its output budget. Input
characters are bounded on every turn. Tool calls use timed futures; cancellation
stops subsequent steps and result delivery, but cannot forcibly terminate an already
running SDK/network call. That call retains the existing transport timeout. Usage
limits use durable actor/environment model-call accounting, not browser counters.

### Conversation and UI decisions

Migration `0041_omni_conversations` adds only private conversation and feedback
tables. Ownership hashes the server's tenant and actor together; new v2 audit
receipts use that same scope. The legacy endpoint retains its earlier actor scope.
History is bounded to 100 turns / 600,000 serialized characters; list shows the
50 latest threads. Default retention is 30 inactivity days, configurable through
`BTX_OMNI_CHAT_RETENTION_DAYS`. Expired threads are inaccessible immediately and
physically pruned on that actor's next list request. Explicit deletion removes
turns, feedback and linked answer receipts, not accepted user memory or business data.
Concurrent append uses version checking. A canceled request is not added to history;
an already-running provider call may complete its private audit.

SSE streams tool progress immediately and validated answer paragraphs only after
validation and persistence. It does not stream raw model tokens. Resume uses stored
turns and referents rather than trusting a browser-supplied history transcript.
Markdown is rendered as escaped React nodes; only HTTP(S) and app links are allowed.
The existing ActionEditor is reused, lazy-loaded and prefilled only. Its save/CRM
paths are unchanged and require the existing user-reviewed submission.

M4 checks: migration applied to task-owned PostgreSQL; full backend 857 passed;
frontend typecheck/lint/build and 88 unit tests passed; three new browser checks
passed (history/deletion, proposal-without-write, cancel/HTML safety). The broader
186-case browser regression run is a separate still-open validation item: baseline
tests predate Profiles naming, profile tabs, Customer Health and SSE. Label/transport
updates preserve assertions, rather than disabling tests. New history and feedback
do not alter personal-memory acceptance, inspection, editing or deletion.

### Evaluation and regression decisions

`tests/evals/omni_chat.yaml` is JSON-compatible YAML 1.2, so the existing Python
standard library can load it without another dependency. The 72 cases execute real
read-tool implementations against the release sample ledger with a scripted provider.
`backend/tests/omni_eval_support.py` checks routing execution, account boundaries,
refusals, privacy, citations and validation. Scripted tool selections do not prove
that a live Gemini model will select those tools; this is an orchestration contract
suite, not a claim of model intelligence. Existing CI discovers the pytest module.

`backend/scripts/omni_live_eval.py` produces per-case full answers, tool calls,
latency, usage, validation and category results. Without a Gemini API key it exits
successfully with an explicit SKIPPED message and makes no calls or report writes.
Live evaluation uses sample data and a report-local private usage ledger. Its
automated behavior checks still require human review for tone and entailment.

Legacy browser assertions that expected rich deterministic conversation without
a configured model are intentionally updated to require the v2 degraded disclosure.
Typed screen/event/relationship context must still be transported, but an unconfigured
model does not fabricate a rich assessment or claim it used an event it did not read.
Account follow-ups remain covered by new fake-provider and persisted-history tests.
The old `/api/omni` compatibility implementation is retained; no old routing logic
was deleted to manufacture a passing evaluation.

Browser test maintenance also corrects existing Profiles navigation versus Customers
page headings, separate profile tabs, Customer Health versus the older Attractiveness
column, portable screenshot paths, and waits for asynchronously mounted profile tabs.
Those changes do not modify scoring, profile rendering or workflow writes. The new
tool audit steps retain the legacy receipt viewer's step/evidence/checksum fields in
addition to argument hashes, result sizes and latency; a regression assertion covers
that compatibility. Chromium occasionally evicts completed SSE bodies from its debug
protocol: legacy receipt tests can inspect the identical persisted turn, without
reissuing the question. Both legacy and new browser tests prefer actual SSE frames;
the fallback carries the original actor header and reads the identical stored turn.
The new browser test also requires SSE content type and actual rendered client output;
API tests assert frame order and unit tests exercise split-byte stream decoding.

Private history endpoints return `Cache-Control: private, no-store`. Conversation
retention does not currently sweep orphaned audit receipts from canceled/concurrent
requests; explicit deletion removes receipts linked to the stored transcript.

Final regression corrections: portfolio-wide questions clear passive account/referent
scope in the client and server, while an explicitly named account still wins. New
unit tests cover that boundary and the existing UI source assertion now requires the
portfolio guard instead of unconditionally forwarding the previous referent. Failed,
denied and timed-out tool attempts are recorded with hashed arguments and a sanitized
failure class; denied rows and exception text are never copied into the result.
