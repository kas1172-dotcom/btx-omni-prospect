# BTX Omni Scoring Rubric v2.0

## Authority and amendments

Converted verbatim (including original worked-example errors below) from the supplied Downloads/BTX_Omni_Scoring_Rubric_v2.0.docx. The DOCX is unchanged. The available source does not contain a resolutions R1–R10 preamble. The following explicit user amendments govern over the source examples and older drafts; no absent resolution text has been invented.

- R1: freshness boundaries include the endpoint; 30-day windows give 10 at age <=7.5 days, 7.5 at <=15, 5 at <=30, and 0/Stale beyond 30. Stale observations become Unknown; preserve historical evidence.
- R2: fixed-weight missing-factor bounds are zero to full weight, never reweighted. Required unknown conditions block eligibility.
- R3: Public Event Risk uses Mitigation, not Reversibility (section 7).
- R4: Internal Commercial Risk is direct-scored (section 8), never 100 minus resilience.
- R5: Action Priority uses section 13 triage classes, not weighted action formulas.
- R6: internal transactions and capacity expire after two days. Historical transaction dates are distinct from the snapshot verification date.
- R7: a newer authoritative source supersedes older evidence; the superseded observation remains history, not an unresolved equal-authority conflict.
- R8: convergence and legal/safety overrides require explicit evidence inputs. Absent inputs grant neither uplift nor override.
- R9–R10: NOT FOUND in the supplied document or user-provided resolution text. Sections 1–18 and explicit user amendments remain authoritative.

Corrected examples: Signal Confidence at nine days is **86.25 High**, at three days **88.75 High**. Overall risk is exactly **62.00**. Delivery Feasibility uses contributions **22.5 + 18.75 + 11.25 + 11.25 + 5 + 3.75 = 72.5 B**. A blocked case can have weighted **78.75 B+** but must display **Blocked**. Band tables govern over inconsistent example narratives.

The executive deck slide 15 and older working draft are superseded where they disagree with this specification.

## Original source text

BTX OMNI

Scoring Rubric

Version 2.0 · September 2026

1. Overview

BTX Omni evaluates nine dimensions of a customer, prospect, opportunity, or risk. Each family answers one question, is scored and displayed independently, and is never averaged into a blended figure. A score belongs to the object it evaluates. 

| Family | Applies to | Question it answers | Displayed as |
| --- | --- | --- | --- |
| Signal Confidence | A single signal | How reliable, specific, current, corroborated, and correctly matched is this evidence? | Qualitative band (High / Medium / Low) |
| Prospect Fit | A prospect organization | Is this generally the type of organization BTX should target? | Percentage |
| Opportunity Priority | A specific pursuit | How worthwhile and timely is this commercial hypothesis? | Score out of 100 |
| PWIN | A qualified deal | How likely is BTX to win this defined pursuit? | Score out of 100 |
| Delivery Feasibility | A qualified deal or solution | Can BTX credibly deliver the defined work? | Letter grade |
| Customer Health | A current or dormant customer | What is the longitudinal health of the BTX commercial relationship? | Status word |
| Risk Severity | A specific risk event | How damaging could this condition be? | Score out of 100 + disposition |
| Action Priority | A task or alert | What requires attention first? | Ranked queue |
| Data Coverage | Any of the above | Do we have enough reliable information to make this assessment responsibly? | Score out of 100, shown beside the primary score |

2. How scoring works

Every weighted family works the same way. Each factor has a maximum point value, its weight. A factor is scored on a 0–100 scale, and its contribution to the family total is weight × (factor score ÷ 100). A 25-point factor scored at 75 contributes 18.75 points. The family total is the sum of every factor’s contribution, out of 100.

All dollar figures are calculated in exact decimal precision and rounded to two decimals only for the final number shown; the underlying value is preserved wherever a threshold or gate depends on it.

When information is missing

| Situation | What happens |
| --- | --- |
| Known | The rule is applied normally. A genuinely bad value of zero is not the same as missing; it is scored as zero. |
| Unknown | No score for that factor. The gap is flagged as a specific research need rather than guessed at. |
| Stale | The factor’s value has expired under its freshness rule (section 3) and is treated as unknown until it is refreshed. The old record is kept for history. |
| Conflicting | Two equally authoritative sources disagree. No score until the more authoritative source is identified or the conflict is resolved and recorded. |
| Not applicable | Only used where a family explicitly defines it (for example, Customer Health does not apply to a prospect). It is never a substitute for missing evidence. |

If any factor is missing, the family does not silently reweight the factors it does know, which would inflate the score. Instead, it shows a range: the low end assumes every missing factor scores zero, the high end assumes every missing factor scores full points. A missing factor that is also a required condition blocks eligibility outright, regardless of where the range falls.

The worked examples use illustrative numbers to show how each calculation works. They are arithmetic demonstrations, not live scores for any real company.

3. Evidence and freshness

Every public or internal signal is checked for two things: is it well-documented and is it still current.

What a signal needs to be well-documented

| Signal type | What it must name to count as specific |
| --- | --- |
| Award or contract change | Recipient, award/instrument ID, type of action, dollar amount with what the amount represents, effective date, and a description of the work. |
| Facility investment or closure | Organization, site or location, type of change, effective date or timeline, and the affected operation. |
| Regulatory or financial event | Legal entity, filing or record ID, event type, effective or report date, and affected scope. |
| Internal commercial change | Customer, source record and period, the measure that changed, its current and comparison values, and the type of change observed. |

How long a signal stays current

Awards, filings, and facility events stay valid for 30 days before they need reverification. Market news and press coverage are treated as time-sensitive and expire after 7 days. Internal transactions and capacity figures move fastest and expire after 2 days. Employment and access claims hold for 30 days. Structural facts about a company or its capabilities (the kind that rarely change) hold for 180 days. 

4. Signal Confidence

High 70–100 · Medium 40–<70 · Low 0–<40

Applies to one public or internal signal at a time. It measures how much to trust the signal, not how important it would be if true. 

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Source reliability | 30 | An authenticated government filing, award record, or governed internal system record scores full points (30). A direct, attributable company statement scores 22.5. An accountable trade publication scores 15. An attributable secondary aggregator scores 7.5. An anonymous or known-unreliable source scores 0. A canonical seller recommendation requires source reliability of at least 15. |
| Entity-match confidence | 25 | A unique authoritative identifier with the correct site or subsidiary resolved scores full points (25). A unique legal name plus address with no conflicting ID scores 18.75. A correct parent company but unresolved site scores 12.5. A fuzzy name match only scores 6.25. An unresolved or contradictory identifier scores 0. A canonical seller recommendation requires at least 18.75 here. |
| Event specificity | 20 | Scored as the share of the signal type’s required fields (section 3) that are actually populated and unambiguous. All fields present scores full points; each missing field lowers the score proportionally. |
| Independent corroboration | 15 | Three or more independently originated sources agree: full points (15). Two sources: 11.25. One source: 3.75. No supporting source: 0, and the signal is held back for review. Syndicated copies, mirrors, and a press release repeating the same filing all count as one source, not several. |
| Freshness | 10 | Scored against the signal’s freshness window (section 3): within the first quarter of the window scores full points (10); the next quarter scores 7.5; the back half of the window scores 5; beyond the window scores 0. |

Example calculation

A federal award-modification record posts, reporting a funding increase on an active program:

| Factor | Points | Why |
| --- | --- | --- |
| Source reliability | 30 / 30 | Primary SAM.gov award-modification record, not a syndicated copy. |
| Entity-match confidence | 25 / 25 | CAGE code matches the registered entity exactly. |
| Event specificity | 20 / 20 | Amount, program name, and effective date are all present and unambiguous. |
| Independent corroboration | 3.75 / 15 | A single primary source; no second independent record yet. |
| Freshness | 10 / 10 | Verified nine days after the modification took effect. |
| Total | 88.75 / 100 · High |  |

A single well-documented primary source can score High without needing independent corroboration to pad the total. Signal Confidence reflects evidential strength, not commercial relevance.

5. Prospect Fit

Strong 75–100 · Relevant 50–<75 · Limited 0–<50

Applies only to a prospect organization, not a current customer. It measures whether an organization is generally the kind of company BTX should target, independent of whether a specific pursuit has been found there yet. 

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Target-cohort match | 30 | The organization sits in an approved primary target market: full points (30). An approved adjacent market: 22.5. An approved exploratory market: 15. Explicitly excluded, or outside every approved market: 0. |
| Manufacturing fit | 25 | Two or more evidenced sites with matching process and component-family overlap: full points (25). One such site: 18.75. Overlap confirmed only at the parent-company level: 12.5. Adjacency in component family only: 6.25. A documented mismatch: 0. |
| Scale | 15 | Trailing twelve-month revenue of $1bn or more: full points (15). $100m–<$1bn: 11.25. $25m–<$100m: 7.5. Above $0–<$25m: 3.75. Confirmed zero: 0. |
| Outsourcing posture | 15 | An active external sourcing channel for the relevant component family: full points (15). Documented external suppliers with the family unspecified: 11.25. A documented mixed make/buy strategy: 7.5. Historical outsourcing evidence only: 3.75. Explicit current captive sourcing: 0. |
| Strategic archetype | 10 | An OEM or prime with manufacturing procurement authority: full points (10). A tier-one subsystem manufacturer: 7.5. Another component manufacturer: 5. A distributor or service intermediary: 2.5. No relevant buying function: 0. |
| Existing BTX access | 5 | A current, two-way buyer conversation: full points (5). A documented, willing internal introducer: 3.75. A prior quote within 365 days: 2.5. A named, relevant contact with no engagement yet: 1.25. Completed research with no access found: 0. |

Example calculation

A private aerospace-manufacturing prospect:

| Factor | Points | Why |
| --- | --- | --- |
| Target-cohort match | 30 / 30 | Private space launch and satellite manufacturing sits in an approved primary target market. |
| Manufacturing fit | 18.75 / 25 | One evidenced facility with real process overlap; a second site is not yet confirmed. |
| Scale | 11.25 / 15 | Revenue in the $100m–<$1bn band with growing manufacturing spend. |
| Outsourcing posture | 11.25 / 15 | Known to use outside manufacturing partners for select hardware. |
| Strategic archetype | 7.5 / 10 | OEM archetype BTX pursues successfully elsewhere. |
| Existing BTX access | 1.25 / 5 | No warm contact yet; a cold-to-warm prospect. |
| Total | 80 / 100 · displayed as 80% |  |

Target market and buying role measure different things, so both are scored. A complete research record can legitimately conclude there is no access yet; that is a true zero.

6. Opportunity Priority

75–100 High priority · 50–<75 Worth developing · <50 Lower priority

Applies to one specific pursuit. It measures how worthwhile and well-timed that commercial opportunity is. Six categories make up the total:

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Program durability | 30 | Made up of the program’s expected horizon (40% of this category), whether the work repeats (30%), how firmly it is committed (20%), and how mature the evidence is (10%). See the leaf table below. |
| BTX manufacturing fit | 25 | Made up of material match (30%), process/tolerance match (30%), certification fit (20%), and volume compatibility (20%). |
| Addressable BTX work | 15 | Made up of component content (40%), repeat-volume potential (30%), cross-BU applicability (20%), and make/buy propensity (10%). |
| Program momentum | 10 | Made up of recent award activity (40%), hiring signals (20%), milestone news (20%), and regulatory developments (20%). |
| Strategic target fit | 10 | A single read on the buyer’s archetype: OEM/prime down to an unlikely buying role. |
| BTX commercial adjacency | 10 | A single read on BTX’s existing commercial history with this organization. |

How each underlying factor is read

| Factor | Full points | Lower bands |
| --- | --- | --- |
| Expected horizon | 10+ years of expected production | 5–9 yrs: 80% · 2–4 yrs: 55% · under 2 yrs or one-off: 25% |
| Repeat pattern | Established, recurring production | Multiple batches, not yet locked in: 70% · a single defined run: 30% |
| Commitment strength | Funded, awarded, and under contract | Budgeted with credible funding: 70% · early-stage/conditional: 40% · funding at risk: 20% |
| Maturity evidence | 24+ months of accepted production | Prototype or shorter production run: 60% · concept-only: 30% |
| Material / process match | Routine work for BTX | Analogous work needing adaptation: 70% · known mismatch: 20% |
| Certification fit | All required certifications met | Minor gap with a dated remedy: 70% · any mandatory gap: 20% |
| Volume compatibility | Within BTX’s normal lot range | Workable but not ideal: 70% · poor fit: 30% |
| Component content | 2+ scoped component families | One family, 2+ components: 75% · one component: 50% · minimal: 20% |
| Repeat-volume potential | $250k+/yr recurring BTX work | $50k–<$250k: 75% · under $50k: 40% · explicit one-off: 20% |
| Cross-BU applicability | Two or more BTX business units | One business unit: 70% · weak or none: 20% |
| Momentum: awards | Funded increase of 10%+ in 90 days | A smaller positive change: 70% · no material change: 50% · reduction/cancellation: 20% |
| Momentum: hiring | 10+ program-linked hires in 90 days | 1–9 hires: 60% · none: 50% · program-linked layoffs: 20% |
| Momentum: milestones | First production or 10%+ volume increase | On-track published milestone: 70% · none identified: 50% · missed milestone: 20% |
| Momentum: regulatory | A dated ruling that materially helps | No change: 60% · a ruling that materially hurts: 20% |
| Strategic archetype | OEM or prime | Tier-one: 80% · unclear fit: 60% · weak/adjacent: 40% · unlikely: 20% |
| Commercial adjacency | Active, multi-BU work in the last 365 days | One active BU: 85% · warm prior customer: 75% · quote or warm contact only: 65% · analogous history elsewhere: 60% · cold prospect: 50% |









Example calculation

An existing customer with an active expansion opportunity:

| Factor | Points | Why |
| --- | --- | --- |
| Program durability | 27 / 30 | Multi-year sustainment program, recurring production, long platform life. |
| BTX manufacturing fit | 20 / 25 | Precision-machined structural content closely matches BTX’s process and certification profile. |
| Addressable BTX work | 11.25 / 15 | Recurring component content spans two sub-systems. |
| Program momentum | 7 / 10 | A recent funding increase plus a facility hiring signal. |
| Strategic target fit | 10 / 10 | Core defense-prime archetype. |
| BTX commercial adjacency | 6.5 / 10 | Existing quote history and a named program-office contact. |
| Total | 81.75 / 100 · High priority |  |

Opportunity Priority, Evidence Confidence, and Data Coverage are always shown side by side and never blended into each other. An opportunity can be high-priority and still low-confidence at the same time.

Qualification gates

Qualified is a Yes/No/Unknown classification, separate from the priority score. Every condition below must pass; Unknown is never quietly treated as Yes.

| Gate | What must be true |
| --- | --- |
| Identity | The organization is uniquely resolved, with the correct subsidiary or site confirmed. |
| Evidence | Every essential assertion (identity, need, capability, timing) is present, with confidence of at least 70. |
| Need | A buyer need or public program requirement is stated in a sourced, dated record, not inferred from component speculation. |
| Capability | Material and process scores are at least 70, and certification fit is at least 70 with no mandatory blocker. |
| Addressable work | At least one specific component family has evidence-linked scope and a credible external sourcing route. |
| Timing | There is an open procurement date, current request, or a documented review window within 180 days. A program end date alone is not enough. |
| No disqualifiers | No explicit no-bid, prohibited transaction, impossible mandatory requirement, or withdrawal. |

Durable

Durable is a separate Yes/No/Unknown classification, layered on top of Qualified. Durable = Yes requires an expected production horizon of five years or more, a repeat pattern of established-recurring or multiple-batches, funded or credibly budgeted commitment, and at least partial-credible maturity evidence, with the underlying program status still current. Any known failure is a No; a missing condition is Unknown, never a silent Yes.

A short-term opportunity can score highly on priority and still fail Durable: an attractive one-off project is exactly the case this gate is built to catch.

Saved views

Qualified & Durable: every record where both gates are Yes. The full durable pipeline.

Durable Best Bets: Qualified and Durable, plus Opportunity Priority of 75 or more, Evidence Confidence of 70 or more, and no missing inputs. The immediate seller queue.

Everything else stays visible in the full research feed rather than disappearing; failing a gate removes an opportunity from these two curated views, not from the product.

7. Public Event Risk

Critical 85–100 · High 70–<85 · Moderate 40–<70 · Low 0–<40

Applies to one independent, negative public event (a contract cancellation, facility closure, layoffs, sanctions, bankruptcy, or a lost recompete).

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Potential impact | 30 | Bankruptcy, a legal prohibition, or cancellation of the entire affected program: full points (30). A facility closure or a 25%+ program reduction: 22.5. A 10–<25% reduction, or a delay of 30+ days: 15. Under 10% reduction, or a 1–29 day delay: 7.5. Confirmed no adverse change: 0. |
| Materiality | 20 | Measured against the larger of the affected share of trailing revenue or current backlog. 50%+ affected: full points (20). 25–<50%: 15. 10–<25%: 10. Above 0–<10%: 5. None: 0. For a prospect, this is measured against the specific pursuit instead. |
| Imminence | 15 | Already in effect, or due within 30 days: full points (15). 31–90 days out: 11.25. 91–180 days: 7.5. 181–365 days: 3.75. More than a year out: 0. |
| Persistence | 15 | A permanent, structural change: full points (15). Expected to last more than a year: 11.25. 91–365 days: 7.5. 1–90 days: 3.75. No remaining effect: 0. |
| Breadth | 10 | The whole enterprise affected: full points (10). Two or more business units: 7.5. Two or more facilities in one business unit: 5. One facility or program: 2.5. An isolated component with no wider effect: 0. |
| Mitigation | 10 | A documented, unavailable remedy: full points (10). The customer confirms no plan exists: 7.5. A documented plan that has not started: 5. Mitigation underway with dated milestones: 2.5. The effect is fully mitigated: 0. |

Example calculation

An SEC filing discloses a facility consolidation that affects a program BTX supplies into:

| Factor | Points | Why |
| --- | --- | --- |
| Potential impact | 22.5 / 30 | A single major program is affected, not the whole customer relationship. |
| Materiality | 15 / 20 | The consolidating facility is a core site for BTX’s content on this program. |
| Imminence | 15 / 15 | The filing states the consolidation is already underway. |
| Persistence | 11.25 / 15 | A facility consolidation is structural, not a one-time event. |
| Breadth | 7.5 / 10 | Two facilities named, not the entire enterprise. |
| Mitigation | 5 / 10 | A remediation plan is documented but has not yet started. |
| Total | 76.25 / 100 · High |  |

8. Internal Commercial Risk

Critical 85–100 · High 70–<85 · Moderate 40–<70 · Low 0–<40

Applies to a current or dormant customer with enough BTX order and quote history to establish a baseline, typically a trailing 12 months. It measures deterioration or exposure directly: a declining, thinning, or friction-prone relationship scores high; a growing, well-covered relationship scores low. Draws on Prism (orders, bookings, revenue) and Paperless (quote aging).

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Commercial momentum | 30 | Trailing-3-month bookings against the prior 3 months. A drop of more than 25% scores full points (30). A drop of 10–25%: 22.5. A drop under 10%: 15. Flat to slightly up (0–<10% growth): 7.5. Growth of 10% or more: 0. |
| Quote and pipeline health | 20 | Share of open quote value that has passed its decision date. More than 50% overdue: full points (20). 25–50%: 15. 10–<25%: 10. Any overdue amount under 10%: 5. Nothing overdue, and a live agreement or recent RFQ is on file: 0. |
| Backlog coverage | 15 | Months of committed backlog against average monthly revenue. Zero backlog: full points (15). Under 1 month: 11.25. 1–<3 months: 7.5. 3–<6 months: 3.75. 6 months or more: 0. |
| Relationship coverage | 15 | Number of actively engaged contact functions. None active: full points (15). One active but no engagement: 11.25. One active function: 7.5. Two active functions: 3.75. Three or more: 0. |
| Concentration | 10 | This customer’s share of the relevant business unit’s revenue. Over 35%: full points (10). 20–35%: 7.5. 10–<20%: 5. 5–<10%: 2.5. 5% or under: 0. |
| Operational friction | 10 | Worst confirmed condition on file. A confirmed critical case, or 60+ days past due: full points (10). 31–60 days past due: 7.5. A repeated case, or 16–30 days past due: 5. One noncritical case, or 1–15 days past due: 2.5. Nothing on file: 0. |

Example calculation

No single dramatic event, but bookings have slipped, quotes are aging, and the relationship has narrowed to one contact:

| Factor | Points | Why |
| --- | --- | --- |
| Commercial momentum | 22.5 / 30 | Bookings down roughly 18% trailing three months. |
| Quote and pipeline health | 10 / 20 | About 15% of open quote value is past its decision date. |
| Backlog coverage | 7.5 / 15 | Roughly 2.5 months of backlog on the books. |
| Relationship coverage | 7.5 / 15 | Down to a single active contact. |
| Concentration | 2.5 / 10 | A moderate, not severe, share of the business unit’s revenue. |
| Operational friction | 2.5 / 10 | One late payment, no open dispute. |
| Total | 52.5 / 100 · Moderate |  |

9. Customer risk rollup and disposition

Public Event Risk and Internal Commercial Risk are always shown on their own; a public risk explanation and an internal risk explanation are never collapsed into one sentence. Where both are complete, they also combine into one overall customer risk figure so a reviewer can triage at a glance.

Public rollup

When more than one active public event applies to the same customer, the rollup starts from the single highest-severity confirmed event, then adds 5 points for one additional material domain (financial/legal, demand/program, operations/site, or supplier/service) or 10 points for two or more, capped at 100. An additional domain only counts if its own severity is 40+ and confidence is 70+. Repeated coverage of the same event never stacks. If every monitoring source completed within its window and found nothing material, the rollup is reported as 0, labeled "No confirmed active public risk", not left blank. If monitoring itself is incomplete, the rollup is left unscored rather than assumed to be zero.

Overall customer risk

Where both Internal Commercial Risk and a confirmed public rollup exist: overall risk = 0.6 × Internal + 0.4 × Public. Add a 5-point convergence uplift only when both scores are 60 or higher and a recorded piece of evidence links them to the same program or site, never inferred just because the dates happen to line up.

Three floors apply after the uplift: a confirmed public score of 85+ sets a floor of 75; a confirmed Internal score of 85+ sets a floor of 80; a confirmed legal prohibition or immediate safety shutdown sets a floor of 85 and blocks execution outright. The final score is the larger of the calculated total or the applicable floor, capped at 100. A prospect with no BTX order history has no Internal Commercial Risk score; only the public reading applies.

Continuing the two worked examples above as if they describe the same customer: Internal 52.5, Public 76.25. Neither reaches 85, so no floor applies; Internal is under 60, so no convergence uplift applies. Overall = (0.6 × 52.5) + (0.4 × 76.25) = 61.85, rounding to 62 · Moderate, leaning toward High.

Disposition matrix

| Severity | Evidence confidence | Disposition |
| --- | --- | --- |
| Critical or High (70+) | High (70+) | Escalate now |
| Critical or High (70+) | Medium or Low | Validate immediately |
| Moderate (40–<70) | High | Act or monitor |
| Moderate (40–<70) | Medium or Low | Research further |
| Low (<40) | High | Monitor |
| Low (<40) | Low | Feed only |

Severity and confidence are read separately, never averaged. Validate Immediately asks someone to confirm the evidence; it is not a claim that the adverse event is already confirmed true. A confirmed mandatory block always outranks a weighted score.

10. Customer Health

Healthy 70–100 · Watch 50–<70 · At risk 30–<50 · Critical 0–<30

Applies only to a current or dormant customer. It measures the overall trajectory of the relationship over time, distinct from Risk Severity, which measures one specific problem and its seriousness, and from Action Priority, which ranks urgency across every open item. A customer can be broadly healthy and still generate one serious risk alert; a relationship can also erode gradually with no single dramatic event.

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Commercial trajectory | 30 | Trailing-3-month bookings against the prior 3 months. Growth of 10%+: full points (30). 0–<10% growth: 22.5. A decline under 10%: 15. A 10–25% decline: 7.5. A decline over 25%: 0. |
| Relationship coverage | 20 | Actively engaged contact functions (a two-way interaction within 90 days). Three or more: full points (20). Two: 15. One: 10. No active contact but one verified role contact: 5. None: 0. |
| Engagement cadence | 20 | Time since the last meaningful touch, against this customer’s expected cadence. At or ahead of pace: full points (20). Up to 1.5× the expected gap: 15. Up to 2×: 10. Up to 3×: 5. Beyond 3×, or no activity in 12 months: 0. |
| Backlog coverage | 15 | Months of committed backlog against average monthly revenue. 6 months or more: full points (15). 3–<6: 11.25. 1–<3: 7.5. Above 0–<1: 3.75. None: 0. |
| Relationship history | 10 | 5+ years with 2 or more fulfilled orders in the last 12 months: full points (10). 2+ years with the same repeat pattern: 7.5. 1+ year with at least one fulfilled order: 5. A shorter or lapsed history: 2.5. An explicitly terminated relationship: 0. |
| Attached risk history | 5 | No material case in the last 12 months: full points (5). All past cases resolved and none repeated within 90 days: 3.75. One unresolved noncritical case: 2.5. Two or more unresolved noncritical cases: 1.25. Any confirmed critical unresolved case: 0. |

Example calculation

A relationship with no single dramatic event, but gradual inactivity and softening bookings:

| Factor | Points | Why |
| --- | --- | --- |
| Commercial trajectory | 15 / 30 | Bookings down under 10% over the trailing three months. |
| Relationship coverage | 10 / 20 | Down to a single active contact. |
| Engagement cadence | 10 / 20 | Roughly twice the normal gap since the last meaningful touch. |
| Backlog coverage | 11.25 / 15 | Solid forward coverage remains on the books. |
| Relationship history | 10 / 10 | Long-standing relationship with a steady repeat-order pattern. |
| Attached risk history | 3.75 / 5 | One minor case on file, already resolved. |
| Total | 60 / 100 · Watch |  |

Healthy describes the weighted relationship pattern; it is not a guarantee that no serious risk exists. Material current risks are always shown alongside Health, never hidden behind it, and a poor Health score never reclassifies a current customer as dormant. Customer status is sourced independently.

11. PWIN

Strong 75–100 · Developing 50–<75 · Weak 0–<50

Applies once an opportunity is a qualified deal, not while it is still being evaluated for priority. PWIN measures how likely BTX is to win a specific, defined pursuit, and requires a validated buyer, requirement, competitive read, and pricing reference before it can be shown.

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Buyer access | 25 | Two-way contact with the actual decision authority: full points (25). Two-way contact with an evaluation-committee member: 18.75. Contact with a named influencer: 12.5. A verified role contact with no interaction yet: 6.25. Confirmed inability to reach the buyer: 0. |
| Competitive position | 20 | A sole-source selection documented by the buyer: full points (20). Incumbent, eligible for renewal: 15. An invited bidder with no documented edge: 10. An unsolicited challenger against a known incumbent: 5. The buyer has excluded BTX: 0. |
| Requirement fit | 20 | Scored as the share of noncritical requirements confirmed met. All critical requirements must separately pass; any critical failure blocks the pursuit outright, and any unknown critical item needs research before scoring continues. |
| Budget and process | 15 | Buyer-confirmed budget, decision date, and evaluation process: full points (15). Budget and date confirmed, process still unclear: 11.25. Budget confirmed, date and process unclear: 7.5. A documented but conditional budget: 3.75. The buyer confirms there is no funding: 0. |
| Price competitiveness | 10 | BTX’s quoted price at 95% or less of the buyer’s target: full points (10). 95–100%: 7.5. 100–110%: 5. 110–125%: 2.5. Above 125%: 0. |
| Track record | 10 | Two or more accepted deliveries in the same family and requirements: full points (10). One: 7.5. Accepted work in an adjacent family: 5. A validated prototype only: 2.5. No relevant performance history: 0. |

Example calculation

| Factor | Points | Why |
| --- | --- | --- |
| Buyer access | 12.5 / 25 | Access to the program manager, not yet the final decision authority. |
| Competitive position | 10 / 20 | A challenger against an entrenched incumbent. |
| Requirement fit | 20 / 20 | Requirement closely validated against BTX capability. |
| Budget and process | 11.25 / 15 | Funded, but the decision process is not fully confirmed. |
| Price competitiveness | 5 / 10 | Roughly in range, not clearly the lowest bid. |
| Track record | 7.5 / 10 | Adjacent, not identical, past performance. |
| Total | 66.25 / 100 · Developing |  |

PWIN is a working estimate until it has been checked against actual BTX win/loss outcomes; it is not a statistically validated win probability. 

12. Delivery Feasibility

A+ 93–100 · A 85–<93 · B+ 78–<85 · B 70–<78 · C 55–<70 · D 40–<55 · F 0–<40

Applies to a qualified deal or a specific proposed solution, once the scope of work is defined well enough to check against real capacity and capability at a named facility.

| Factor | Weight | How the score is set |
| --- | --- | --- |
| Capability match | 30 | Every required process, material, and piece of equipment is available: full points (30). One noncritical gap with a funded, dated remedy: 22.5. Two or more such gaps: 15. Gaps with a proposed but unfunded remedy: 7.5. Any required process unavailable by the need date: 0. |
| Schedule feasibility | 25 | Ratio of net available hours to required hours. 1.25 or higher: full points (25). 1.10–<1.25: 18.75. 1.00–<1.10: 12.5. 0.90–<1.00: 6.25. Under 0.90: 0, and capacity mitigation is required before the work can be committed. |
| Material readiness | 15 | The most constrained critical material is ready 30+ days early: full points (15). 14–29 days early: 11.25. 1–13 days early: 7.5. Exactly on the need date: 3.75. Late, with no approved substitute: 0. |
| Quality and certification | 15 | Every requirement is valid through delivery and buyer approval is current: full points (15). Certificates valid, buyer qualification still scheduled: 11.25. A renewal is planned before expiry with a dated owner: 7.5. A qualification plan exists with no dated milestone: 3.75. A mandatory requirement cannot be met by the start date: 0. |
| Margin | 10 | (Quote value − estimated total cost) ÷ quote value. 30%+ margin: full points (10). 20–<30%: 7.5. 10–<20%: 5. 0–<10%: 2.5. Negative margin: 0. |
| Coordination | 5 | A single site with an accountable owner, or every cross-site handoff has an owner and a date: full points (5). All owners assigned but one date unresolved: 3.75. One owner unresolved: 2.5. Multiple owners unresolved: 1.25. Conflicting site commitments: 0. |

Example calculation

| Factor | Points | Why |
| --- | --- | --- |
| Capability match | 24 / 30 | Process and certifications already in place at the relevant facility. |
| Schedule feasibility | 15 / 25 | Tight given current backlog at that facility. |
| Material readiness | 11.25 / 15 | Materials available with a moderate lead time. |
| Quality and certification | 13.5 / 15 | Already certified for this class of work. |
| Margin | 5 / 10 | Marginal but workable at the likely price point. |
| Coordination | 4 / 5 | Single-site delivery. |
| Total | 72.75 / 100 · displays as B |  |

13. Action Priority

Action Priority ranks what a person should address first, across every open task or alert.

How the queue is ordered

Completed, dismissed, snoozed, duplicate, and no-longer-valid items are filtered out first. What remains is sorted into four classes, in this order:

Class 0: a confirmed safety, legal, or stopped-shipment issue.

Class 1: a risk disposed as Escalate now.

Class 2: a risk disposed as Validate immediately.

Class 3: every other executable piece of seller work.

Within a class, a fully assessed item is always shown ahead of one with missing inputs. Fully assessed items are then sorted by their underlying score (an opportunity’s Priority, a risk’s Severity, or a customer’s Health trend) from highest to lowest; incomplete items are sorted by the top of their possible range. Ties break by due date (soonest first, missing dates last), then by when the item was created, then by a stable ID so the order never jumps around on reload.

Example: three open items on the same customer

| Rank | Item | Class and reasoning |
| --- | --- | --- |
| 1 | Review facility-consolidation risk | Class 1: disposed as Escalate now. Outranks every class-3 item regardless of score. |
| 2 | Validate expansion RFQ | Class 3, but the highest-priority complete item in that class (Opportunity Priority 94, high confidence). |
| 3 | Re-engage cooling customer | Class 3, lower underlying priority than the RFQ, unowned; kept visible rather than aging out. |

14. Data Coverage

Complete 100 · Partial 70–<100 · Limited 0–<70

Data Coverage answers a narrower question than it sounds: does this specific assessment have enough usable information behind it? It is not a measure of company quality, source popularity, or how many systems happen to be connected; a single authoritative source, fully populated, can and should show Complete.

Coverage is calculated from the same factor weights as the family it accompanies: each factor is worth its normal weight if the underlying data is present, current, unambiguous, and available in time, and worth zero toward coverage if not. Coverage is the share of the total possible weight that is actually backed by usable data, expressed out of 100. Missing two factors worth 15 points combined, for example, brings coverage to 85, even if the family’s point score itself cannot be finalized yet.

Signal Confidence, Opportunity Priority, Prospect Fit, PWIN, Delivery Feasibility, Customer Health, and Risk Severity each carry their own Data Coverage reading, shown beside the primary score, never averaged into it. Public and internal risk coverage are tracked separately so a gap in one is never hidden inside a combined average.

15. Explainability standard

Every assessment, in every family, presents five things together:

The result, and the scoring-rule version that produced it.

Factor contributions and the supporting evidence behind each one.

Missing information and eligibility status, where applicable.

The reasons for the result, in plain language that matches the factor contributions.

What would change the result.

A generative model may render the plain-language explanation from the computed factor contributions, using the stored evidence and the exact numeric trace, but it narrates the result.

16. Worked decisions

| Situation | What Omni shows |
| --- | --- |
| A single strong primary source | Signal Confidence 88.75 · High, even with only one source, because that source is a primary authenticated record. Still worth checking commercial relevance separately. |
| A qualified, durable pursuit | Opportunity Priority 81.75, Evidence Confidence High, Durable = Yes. Appears in Durable Best Bets only once every qualification check has passed. |
| Incomplete manufacturing fit | Known contributions total 68 of 100 possible; 15 points of weight are still missing. Priority is shown as a range, not a single number, until the missing fit checks are resolved. |
| A quietly deteriorating customer | Customer Health 60 · Watch. The customer’s status stays Current; a soft Health score never reclassifies it as dormant. |
| An otherwise strong delivery blocked by one certificate | The weighted total would be a B+, but a failed mandatory certification shows Blocked instead; a mandatory failure always overrides a favorable average. |
| An RFQ next to an Escalate Now risk | The risk item ranks first in the Action queue regardless of the RFQ’s higher underlying score; disposition class always beats a raw number. |
| An uncalibrated PWIN | PWIN 66.25 · Developing. Never shown as "66% likely to win"; it is an index, not a validated probability, until checked against real outcomes. |

17. How scores attach to the product

The same subject, evaluated at the same moment with the same rule version, must produce the same assessment everywhere it appears: Today, a customer or prospect profile, the map, the relationship graph, and Actions. Moving between screens never triggers a second, different calculation.

| Journey | Families involved |
| --- | --- |
| Planning a regional customer visit | Prospect Fit; Customer Health where applicable; Data Coverage; Action Priority for prep tasks. |
| Cross-BU growth and budgeting | Opportunity Priority; Prospect Fit for new organizations; Customer Health for existing ones; PWIN only after qualification. |
| Market and partnership research | Prospect Fit and Customer Health where eligible; Data Coverage. No M&A-specific score exists. |
| A public signal creates a new prospect | Signal Confidence; Prospect Fit once inputs exist; Data Coverage; Opportunity Priority only after a pursuit is defined. |
| A customer signal opens an expansion | Signal Confidence; Opportunity Priority; Data Coverage; later, PWIN and Delivery Feasibility. |
| External risk triggers a briefing | Signal Confidence; Public Event Risk; the customer risk rollup once complete; Action Priority; Data Coverage. |
| Internal risk leads to a recovery action | Action Priority; Customer Health or Internal Commercial Risk once complete; Delivery Feasibility for a defined solution; Data Coverage. |
| Relationship paths support expansion or a new contact | Route ranking is calculated separately from all nine families; Opportunity Priority, PWIN, or Data Coverage still apply to the underlying subject. |

Geographic distance can help choose visit stops, but it never changes Prospect Fit or Opportunity Priority. Relationship-route ranking is its own versioned calculation and is never relabeled as PWIN or Signal Confidence.

18. Data this depends on

Every family above ultimately depends on the same handful of BTX data sources being connected and current:

| Source | What it supplies |
| --- | --- |
| Prism (ERP) | Orders, bookings, revenue, and backlog by customer and business unit. |
| Paperless (quoting) | RFQ and quote records, revisions, pricing, and decision dates. |
| Contact and engagement data | Contacts, engagement history, and deal activity, from agentic public research or other BTX systems. |
| BTX facility records | Named facilities, process and material capability, certifications and their expiry, and net capacity. |
| Public sources | SAM.gov, USAspending.gov, SEC filings, WARN Act notices, and trade press. |




