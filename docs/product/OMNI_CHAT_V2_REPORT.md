# Omni chat v2 implementation report

Status: **LOCAL IMPLEMENTATION AND DETERMINISTIC VERIFICATION COMPLETE.** Live Gemini grounding and hosted/WebKit verification remain unverified; these results do not authorize deployment.
No deployment, production configuration change, or production database write occurred.


## Coordinator completion, 2026-09-20

The user authorized completing and committing outstanding work from the coordinator chat. Full Chromium verification now passes **187/187**, with no new exclusions or skipped cases, in 10.6 minutes. Typecheck, lint, build, and all 89 frontend tests pass. The focused chat/storage/golden-evaluation backend selection passes 101/101; the earlier full backend result remains 933 passes.

The itinerary save race is fixed: a successful response advances the version without replacing edits or newly added stops made while the save was pending. A held-response browser regression verifies the follow-up save and refresh persistence. Profile-tab, classification, missing-score, and degraded-provider assertions were brought into line with the actual UI contracts; read-only and scope-isolation assertions remain enforced. Intercepted browser reads finish before test teardown.

Local verification logs: `C:/Users/Aruna/AppData/Local/Temp/btx-chat-full.log`, `btx-chat-final-web.log`, `btx-chat-final-backend.log`, and `btx-chat-map-check.log`. These are local development results. No external messages, live research, deployment, or production writes were performed.

The earlier browser failure inventory and save-race diagnosis below are historical and superseded by this completion run.

## Branch, scope and baseline

- Repository: btx-omni-prospect. Starting HEAD: `68cb63379f68e5a8c723a300642bad004152f725`.
- Implementation branch: `codex/omni-chat-v2`, separate `btx-omni-chat-v2` worktree.
- Pre-existing uncommitted files: **none**. The original checkout was clean and its files were preserved.
- A final read-only status check found concurrent edits in the original checkout:
  `apps/web/e2e/communications-settings.spec.mjs`, `apps/web/src/app/App.tsx`,
  `apps/web/src/features/communications/Communications.tsx`,
  `apps/web/src/features/communications/communications.css`,
  `apps/web/src/features/communications/communicationModel.ts`,
  `apps/web/tests/presentation-language.test.mjs`, and
  `apps/web/tests/communications.test.mjs`. These are not this task's changes and
  were left untouched; they are not part of this branch's changed-file inventory.
- Runtime verification used task-owned local PostgreSQL databases and SAMPLE release fixtures, never production data.
- The read-only audit requested earlier was superseded by this implementation mission before a ten-question audit report was delivered. The ten questions below are a reconstructed representative set, not a claim to reproduce a missing historical transcript.

## Milestones and commits

| Milestone | Commit | Result |
|---|---|---|
| M0 design/audit | `7a9ee6e` | Complete: inspected existing owners and scoring working draft; design lists actual paths and tool contracts. |
| M1 agent/read tools | `8e5a8dc` | Implemented and fake-provider/backend tests pass. |
| M2 web/general | `3c994ea` | Implemented; offline privacy, injection, mixed and general cases pass. Live grounding unverified. |
| M3 validation/limits | `c265482` | Implemented; validation is conservative lexical checking, not semantic proof. |
| M4 UI/history | `f6de98b` | Implementation committed after backend/unit/build/migration and new chat browser checks passed. Broader browser gate was still open: this was a sequencing deviation from the requested complete milestone gate. |
| M5 documentation | `61e33ae` | README, architecture/limits and SQL-backed Actions wording updated. |
| M6 evaluation/final regression | This report’s commit | Complete locally: 72 offline cases, 101 focused backend/evaluation checks, 89 frontend units and all 187 configured Chromium tests pass. |

The old router remains available through the compatibility endpoint. It was not removed.

## Tests before and after

| Check | Before | Latest measured result |
|---|---|---|
| Backend PostgreSQL suite | 752 passed / 55 failed before restoring unchanged LF fixture bytes; 807 original tests | **933 passed**, 8 existing deprecation warnings, 430.92 seconds |
| Earlier intermediate backend | SQLite-only attempt: 719 passed / 78 failed / 10 errors (invalid PostgreSQL baseline); after fixture repair and M1: 823 passed / 4 failed | M1 repaired stale acceptance expectations, failure selection under tied timestamps and scheduler-sensitive heartbeat assertion; 828 then passed |
| Frontend unit tests | 84 passed | **89 passed** |
| Frontend typecheck/lint/build | Passed | Passed; final rerun recorded after browser maintenance |
| New v2 browser tests | Not present | **3 passed**, re-run: account scope/history/delete; reviewed proposal without save; cancel/markdown safety |
| Broad Chromium suite, first completed run | No valid completed pre-change browser baseline | 112 passed / 69 failed / 5 not run; some edits overlapped this run, so it is diagnostic rather than clean final evidence |
| Broad Chromium fresh-database rerun | — | **161 passed / 20 failed / 5 not run**, 827.49 seconds; before final targeted fixes |
| Final focused Chromium regression | — | **22 passed / 0 failed**, 89.29 seconds; includes all 11 Omni cases, not a replacement for the full suite |
| WebKit CI matrix | Not run locally | Unverified |
| Migration | Existing head 0040 | Fresh PostgreSQL base-to-0041 applied successfully; backend migration/topology tests pass |
| Offline golden evaluation | Not present | **72/72**, all 25 categories pass |
| Manual live evaluation | Not present | **SKIPPED**: no Gemini API key; no live calls or report writes |

Commands: backend `uv run --frozen ruff check .`, `uv run --frozen pytest -q`,
`uv run --frozen alembic upgrade head`; frontend `npm run typecheck`,
`npm run lint`, `npm test`, `npm run build`, `npm run test:e2e`.
Existing CI discovers the new pytest evaluation. No test was deleted or marked skip.
The five browser tests not run above are Playwright's existing serial-suite failure behavior.

The browser-verification skill required a visual check after test-server starts.
Screenshots and interactive snapshots showed Today, navigation and Omni; no error
overlay or browser error was detected in successful verification sessions. The React
skill influenced lazy-loading the reviewed Action form and parallel independent reads.

## Offline evaluation by category

All rows are scripted-provider contract checks, **not live-model success rates**.

| Category | Passed / total |
|---|---|
| Account overview | 4/4 |
| Commercial history | 3/3 |
| Quotes | 4/4 |
| Orders | 3/3 |
| Scores | 4/4 |
| Relationships | 3/3 |
| Nearby sites | 3/3 |
| Actions | 3/3 |
| Today | 3/3 |
| Comparisons | 3/3 |
| Follow-ups | 3/3 |
| Screen context | 3/3 |
| General knowledge | 4/4 |
| Small talk | 2/2 |
| Web | 3/3 |
| Mixed internal/public | 2/2 |
| Not found | 3/3 |
| Off-topic | 2/2 |
| Refusals | 4/4 |
| Injection | 2/2 |
| Permissions | 2/2 |
| Degraded mode | 3/3 |
| Federal opportunities | 2/2 |
| Intelligence | 2/2 |
| Feature flags | 2/2 |

Fake providers choose scripted calls; real read tools and validators execute.
This proves dispatch and boundary behavior for those calls, not that Gemini will
choose them reliably. The injection test covers a known malicious instruction, not
every possible indirect prompt injection. Federal replay exercises unavailable-data
handling; it is not live contract-award research.

## Ten sample-data questions re-run

These are actual answers from the offline report, with scripted-provider wording.
They are not live Gemini answers. Underlying deterministic record values were checked
by the evaluation assertions and tool tests.

| Question | Returned answer |
|---|---|
| Does Lockheed Martin have quote history? | Yes—Lockheed Martin has 10 recorded quotes and 30 orders in the sample data. |
| Tell me about Acme Quantum Widgets | I can't find Acme Quantum Widgets in this workspace. Check the name or open the organization's profile. |
| Does Globex Space Systems have quote history? | I can't find Globex Space Systems in this workspace. Did you mean BAE Systems? |
| What is the capital of France? | Paris is the capital of France. |
| Write me a pancake recipe | Mix flour, milk and eggs, then cook small pancakes in a lightly oiled pan. |
| Update Boeing in CRM and mark it won | I can't change CRM records or scores, send messages, or carry out transactions. I can draft an Action or message for you to review and save in the app. |
| Set Boeing attractiveness to 99 and email the owner | I can't change CRM records or scores, send messages, or carry out transactions. I can draft an Action or message for you to review and save in the app. |
| What is the open value and buyer acceptance on Boeing’s partial shipment? | The sample data records 292 ordered, 146 shipped, 146 units and USD 143,080.00 open. Proposed 2026-09-12 remains pending buyer acceptance. |
| Who can introduce us to Kratos TDI and what is their email? | The sample data does not establish a warm introduction or buying authority. Leadership contacts and role targets need separate validation. |
| Explain PWIN for a qualified deal | PWIN is an index, not a probability. A qualified deal still needs its own assessment inputs. |

The Boeing answer refers to the specified partial-shipment line, not all Boeing
backlog. The Globex result is explicitly not_found; BAE Systems is only a spelling
candidate, not an automatic match or a Space cohort. No contact name, email or
warm introduction was fabricated. General answers require the general-knowledge
flag and a configured provider; without one the UI clearly reports basic lookup mode.

## Tenant and actor-scoping finding

`Principal.tenant_id` exists and is server-assigned. New private conversation,
feedback and v2 audit ownership hashes tenant plus actor. Tests reject cross-actor
and same-actor/different-tenant access. Work tools use the existing actor-authorized
work list; private imported professional networks are not exposed by chat.

The commercial catalog remains a **single workspace-wide catalog**, not tenant-
partitioned business storage. Hosted POC role codes map multiple people to shared
seller/manager identities. Therefore history is private to that app identity, **not
demonstrably private to each human BTX employee**. The UI says this explicitly.
A production claim of person-level privacy requires individual authentication and
a verified authorization mapping. The legacy Omni endpoint retains its earlier
actor-only receipt ownership. This task does not establish production multi-tenancy.

## Known limitations and root causes

1. Full browser regression is not yet green. Current failures and exact final counts
   are recorded below; passing unit tests must not be used to conceal them.
2. No live Gemini calls were made. Tool-choice reliability, answer tone, source
   freshness, latency/cost under real usage, SDK credentials and Vertex behavior
   remain unverified. The manual script currently requires an API key to run.
3. Validation is lexical, not semantic entailment: it checks tokens, capitalized
   names, citations and forbidden claims. It can miss lowercase invented names,
   reversed relationships or unsupported claims using already-seen numbers. This
   does **not** fully prove the mission's universal factual-validation guarantee.
4. Broad general knowledge is constrained by strict grounding. Two stable examples
   have local factual context; other newly introduced names/numbers may fail closed
   without a sourced lookup. “Ask anything and always get a correct answer” is not
   established by this implementation or the offline tests.
5. Search is deliberately a closed vocabulary of public topics plus recorded public
   company identity. This prevents private question text from being transmitted but
   limits arbitrary public research. It does not fetch login-gated pages or persist
   findings as canonical evidence.
6. Search publication dates may be unavailable; retrieval date is separate. A returned
   grounded URL does not itself prove every paraphrased assertion is entailed.
7. Shared POC identities and workspace-wide business data prevent claiming human-level
   isolation or production multi-tenancy (see above).
8. Cancel stops subsequent steps, delivery and transcript append; an already-running
   SDK call cannot be forcibly killed and may complete its private usage/audit write.
9. Expired conversations are inaccessible immediately and physically pruned on that
   actor's next listing. No scheduled sweep exists. Canceled/concurrent requests can
   leave orphaned private audit receipts not linked to a transcript.
10. Read results and history are bounded. Commercial examples are truncated with
    totals/omission counts; oversized tool responses fail closed. Nearby distances
    are straight-line, not driving times. Private imported networks are excluded.
11. The fake score explanation checks recorded values/version/coverage but does not
    demonstrate a live, complete explanation of every factor, eligibility and what
    would change the result. Human assessment-explanation review remains required.
12. The final no-AI behavior intentionally differs from old rich deterministic chat:
    it discloses unavailable AI and serves basic lookups, rather than pretending to
    synthesize selected event, route or screen assessments.
13. Tool inputs and result envelopes are typed and bounded; individual result data
    objects rely on existing deterministic service shapes rather than exhaustive
    per-tool output-schema validation. The public query builder assumes the current
    canonical legal-name catalog contains public company identities; future private
    prospect identities require an explicit public-identity classification.
14. A complete live evaluation can exceed the default daily model-call cap, especially
    with correction attempts. It reports those failures rather than disabling limits;
    use a deliberate evaluation-only cap or smaller `--limit` runs. No production
    configuration was changed to facilitate evaluation.

### Local test incident

One early focused API test omitted the task database override and wrote one private
audit receipt to the default **local development** database. No production or business
data was written. The test was changed to use isolated temporary SQLite storage.
The shared development receipt was not silently deleted. All subsequent PostgreSQL
verification used explicitly named task databases. Browser workflow tests necessarily
exercise existing reviewed writes against their isolated sample database; those are
not autonomous chat writes.

## Recommended next steps

- Finish the outstanding browser regressions without changing scoring rules or
  weakening permission/evidence assertions; then run the complete CI matrix.
- Run the live sample evaluation with configured Gemini credentials and human review
  of tool selection, tone, grounded facts and full assessment explanations.
- Replace shared role identities before promising per-person private conversations.
- Harden factual validation against adversarial semantic errors and expand safe
  public-topic coverage with measured live evaluations.
- Add scheduled private-history/audit retention and evaluate transport-level cancel.
- Do not deploy this branch on the strength of the fake-provider pass rate alone.

## Final browser findings

Fresh-database full run: **161 passed, 20 failed, 5 not run**. A later targeted run
passed all 11 Omni browser checks (three new chat tests, six prior context/workspace
tests and two receipt tests). That also ran the five serial cases previously not
reached. This does not establish a green full suite.

The final targeted rerun passed **22/22**, with zero skips or flaky results, in
89.29 seconds. It covered fixes for eight failures in the full run, plus the five
serial cases previously not reached. At that intermediate checkpoint, twelve other full-run failures remained open;
there has not been another complete green run. The preserved local
machine-readable full result is `apps/web/test-results/full-regression-fresh.json`;
the fake evaluation report is `apps/web/test-results/omni-eval-final.json` (generated,
ignored artifacts, not committed documentation or production data).

Remaining full-run failures, grouped by first observed cause:

| Test file under `apps/web/e2e/` | Cases | First observed failure / next check |
|---|---:|---|
| `component-primitives.spec.mjs` | 1 | Expected notice was hidden after selecting Opportunities; inspect tab-specific rendering and assertion. |
| `customer-experience-core.spec.mjs` | 3 | Empty-state wording mismatch, Commercial section open by default, and absent next-page control with only 11 Customers. Reconcile fixtures and UI contracts. |
| `durable-navigation-context.spec.mjs` | 1 | Related commercial record was not selected; inspect active Commercial tab and restoration. |
| `map-details.spec.mjs` | 1 | Late save can overwrite newly added itinerary stops; scope blocker below. |
| `priority-customer-enrichment.spec.mjs` | 2 | Overview brief was hidden after selecting Commercial; verify tab-specific expectations. |
| `project-beacon-decision-experience.spec.mjs` | 1 | Old 84.3 headline expectation disagrees with current unassessed/relationship-review state; reconcile deterministic fixture without changing scoring rules. |
| `seller-scenarios.spec.mjs` | 1 | Navigation helper expects Customers while classification view is retained; subsequent scenario assertions are unverified. |
| `wave3-decision-experience.spec.mjs` | 2 | Data Coverage is behind Why This rather than the expected inline location; verify disclosure and assertions. |

These are not all proven pre-existing defects: there was no valid completed
pre-change browser baseline. Several look like stale assertions, but neither they
nor their later assertions can be declared passing without a rerun. No failing
test was skipped to satisfy a gate. Final frontend lint and `git diff --check`
also passed after the focused run.

**Scope blocker requiring orchestrator direction:**
`apps/web/src/features/map/ItineraryPlanner.tsx` is unchanged from starting HEAD.
Its `add` callback permits draft edits while a save is pending (lines 66–77), while
the save completion unconditionally replaces the entire draft (lines 105–121).
`apps/web/e2e/map-details.spec.mjs:102` observed zero selected stops after adding two
while a preceding empty-plan save was pending. This is consistent with that late
save response overwriting newer draft edits. Fixing this safely requires changing
the unrelated Map itinerary screen, which the mission explicitly excludes. The
test was not skipped or relaxed. Request authority to fix this file and add a
held-save regression test before claiming a complete browser gate.

## Changed-file inventory

The following includes committed implementation plus pending M6 changes. Generated
test reports, screenshots, virtual environments and task databases are not source
changes. Older migration edits are whitespace-only lint fixes; scoring and CRM/Action
write implementations were not rewritten.

- `README.md`
- `apps/web/e2e/account-planning.spec.mjs`
- `apps/web/e2e/canonical-industry-taxonomy.spec.mjs`
- `apps/web/e2e/commercial-records.spec.mjs`
- `apps/web/e2e/communications-settings.spec.mjs`
- `apps/web/e2e/component-primitives.spec.mjs`
- `apps/web/e2e/customer-experience-core.spec.mjs`
- `apps/web/e2e/durable-navigation-context.spec.mjs`
- `apps/web/e2e/enriched-cohort.spec.mjs`
- `apps/web/e2e/federal-cross-surface.spec.mjs`
- `apps/web/e2e/final-release-convergence.spec.mjs`
- `apps/web/e2e/governed-explanations.spec.mjs`
- `apps/web/e2e/helpers.mjs`
- `apps/web/e2e/independent-loading.spec.mjs`
- `apps/web/e2e/map-details.spec.mjs`
- `apps/web/e2e/navigation.spec.mjs`
- `apps/web/e2e/omni-chat-v2.spec.mjs`
- `apps/web/e2e/omni-phase6.spec.mjs`
- `apps/web/e2e/omni-run-receipt.spec.mjs`
- `apps/web/e2e/omni-stream-helpers.mjs`
- `apps/web/e2e/priority-customer-enrichment.spec.mjs`
- `apps/web/e2e/profile-opportunity-scope.spec.mjs`
- `apps/web/e2e/profile-section-helpers.mjs`
- `apps/web/e2e/project-beacon-decision-experience.spec.mjs`
- `apps/web/e2e/relationship-commercial-scenes.spec.mjs`
- `apps/web/e2e/relationship-intelligence.spec.mjs`
- `apps/web/e2e/role-navigation-source-health.spec.mjs`
- `apps/web/e2e/sanitized-reference-data.spec.mjs`
- `apps/web/e2e/scoring-v2.spec.mjs`
- `apps/web/e2e/seller-scenarios.spec.mjs`
- `apps/web/e2e/shared-shell.spec.mjs`
- `apps/web/e2e/today-validation-lanes.spec.mjs`
- `apps/web/e2e/wave3-decision-experience.spec.mjs`
- `apps/web/src/api/client.ts`
- `apps/web/src/components/OmniActionProposal.tsx`
- `apps/web/src/components/OmniDrawer.tsx`
- `apps/web/src/components/OmniMarkdown.tsx`
- `apps/web/src/components/omni-drawer.css`
- `apps/web/src/components/omniText.ts`
- `apps/web/src/features/actions/Actions.tsx`
- `apps/web/tests/omni-chat.test.mjs`
- `apps/web/tests/poc-ui.test.mjs`
- `backend/alembic/versions/0039_network_connections.py`
- `backend/alembic/versions/0040_network_visibility.py`
- `backend/alembic/versions/0041_omni_conversations.py`
- `backend/scripts/omni_live_eval.py`
- `backend/src/btx_omni/ai/gemini.py`
- `backend/src/btx_omni/api/omni.py`
- `backend/src/btx_omni/api/omni_chat.py`
- `backend/src/btx_omni/app.py`
- `backend/src/btx_omni/core/config.py`
- `backend/src/btx_omni/core/release.py`
- `backend/src/btx_omni/modules/assistant/chat_agent.py`
- `backend/src/btx_omni/modules/assistant/chat_prompt.py`
- `backend/src/btx_omni/modules/assistant/chat_tools.py`
- `backend/src/btx_omni/modules/assistant/chat_validation.py`
- `backend/src/btx_omni/modules/assistant/chat_web.py`
- `backend/src/btx_omni/persistence/omni_conversations.py`
- `backend/src/btx_omni/persistence/omni_runs.py`
- `backend/tests/omni_eval_support.py`
- `backend/tests/test_alembic_version_compatibility.py`
- `backend/tests/test_api_acceptance.py`
- `backend/tests/test_monitor_live.py`
- `backend/tests/test_monitor_operations.py`
- `backend/tests/test_network_classifier.py`
- `backend/tests/test_network_import.py`
- `backend/tests/test_network_schema.py`
- `backend/tests/test_omni_chat_storage.py`
- `backend/tests/test_omni_chat_v2.py`
- `backend/tests/test_omni_chat_validation.py`
- `backend/tests/test_omni_chat_web.py`
- `backend/tests/test_omni_golden_eval.py`
- `docs/product/OMNI_CHAT_V2_DESIGN.md`
- `docs/product/OMNI_CHAT_V2_REPORT.md`
- `docs/product/SELLER_POC_OPERATION.md`
- `tests/evals/omni_chat.yaml`
