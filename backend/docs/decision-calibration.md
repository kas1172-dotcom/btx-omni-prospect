# Deterministic POC decision configuration

Version: `BTX_DECISION_FAMILIES_POC_1`. Owner: `modules/scoring/families.py`.
These are provisional indices, not probabilities or Jamie-approved calibration.
Account Attractiveness retains its existing `account-attractiveness-v1` owner.

Signal Confidence uses source/entity/specificity/corroboration/freshness weights
30/25/20/15/10. Public Risk Severity uses impact/materiality/imminence/persistence/
breadth/reversibility weights 30/20/15/15/10/10. Internal risk uses momentum/
pipeline/backlog/engagement/concentration/friction weights 30/20/15/15/10/10.
These follow the latest supplied scoring decisions, superseding earlier examples.

Opportunity Priority reuses the six structural factor definitions and weights,
but is assessed for a specific opportunity, not averaged into an account score.
Qualification and durability require separate gates; weighted scores cannot
overrule failed identity, evidence, scope or execution prerequisites.

The supplied inputs do not specify complete numerical calibration for PWIN,
delivery or action priority. Initial explicit POC defaults are:

- PWIN: buyer commitment25, solution fit20, commercial position20,
  competitive position20, decision timing15. Requires a qualified deal and all
  factors. Display as an uncalibrated pursuit index, never an empirical percentage.
- Delivery: qualification40, capacity30, materials20, logistics10. Requires all
  factors and no blocking constraint. A capability edge is not capacity evidence.
- Action: impact40, urgency30, readiness20, scope10. Its value does not authorize
  execution, assign an owner or establish contactability.
- Customer Health: health-oriented longitudinal inputs use the six internal-risk
  category weights. Do not substitute opportunity value or public-event count.

Other families require at least70% of their fixed applicable factors. Above that
gate, known weights are normalized; missing factors retain null points and remain
in the coverage denominator. This threshold/reweighting is a POC interpretation,
not an industry standard. Every scored factor requires evidence and a readable
reason. Input-specific coverage must additionally retain the fields required to
establish each factor; a name/domain alone cannot qualify a commercial decision.

Public risk roll-up deduplicates underlying event IDs. The maximum active event
gets +5 for a second material domain, +10 for three material domains or two severe
domains, capped at100. Material>=40 and severe>=70 are provisional. No public
events means unknown, not zero risk. Conflicting copies require resolution.

`BTX_FULFILLMENT_POC_1` computes remaining quantity after dated shipments and
cancellations; accepted quantity and recognized revenue remain separate. A missed
commitment blocks repeating that commitment; a proposal without buyer acceptance
cannot be described as accepted. Historical acceptance is not spare capacity.

Release limits: these core rubrics require canonical input derivation, sensitivity
qualification and end-to-end seller tests before release. Formula unit tests alone
do not qualify their application to real records or external provider outputs.

## Commercial input adapter POC assumptions

The twelve supplied months do not establish trailing-year-over-prior-year changes.
Keep those annual comparison fields unknown. The initial within-history momentum
measure compares the latest three recorded months of bookings with the preceding
three; health points are clamp(50 + 100*change_ratio), risk points are
clamp(-200*change_ratio). These are separate orientation rules, not an opportunity
score or a claim of annual growth.

Historical pipeline progress uses WON value / (WON + LOST value), from current
governed quote revisions. OPEN and EXPIRED are not assumed losses. Historical
conversion is not PWIN. Expected future booking targets remain unknown.

Backlog timeliness uses overdue unshipped/un-cancelled firm value / total open
firm value. A zero open balance is fully fulfilled context, not automatically
healthy future demand. Current qualification/capacity are never inferred from it.

Role-based interaction recency: health100 within14days,70 within30,40 within60,
10 beyond60; risk is the corresponding distance from100. Functional real-person
coverage and accountable user ownership remain separate unknown required fields.
No role interaction establishes contact with a researched named person.

Concentration uses the largest program's share of actual recognized revenue in
the supplied account history. Health is 100-share, risk is share. This describes
the scenario's concentration, not the account's share of all BTX sales. Payment
friction uses overdue unpaid invoice balance / total currently outstanding balance;
when all invoices are settled, known observed unpaid balance is zero. Credit limit
and quantified quality exposure remain unknown, not zero.

Every ratio requires an observed nonzero denominator or an explicit complete
ledger condition. Each adapter declares required and observed field slots;
coverage now uses these slots as well as availability of factor points. A partial
factor cannot hide missing source fields. Effective weights/contributions are
returned separately from configured contributions when normalization is permitted.

Action impact initially uses linked remaining-order or quoted-opportunity value
relative to account TTM revenue, capped at100 points at10% exposure. This is review
exposure, not expected loss or recognized revenue. Due-date urgency: overdue100,
within7days80, within14days60, within30days40, later20. Unknown due dates remain
unknown. Evidence resolution does not invent an assigned user or approve execution.
These curves are provisional POC choices requiring business validation.
