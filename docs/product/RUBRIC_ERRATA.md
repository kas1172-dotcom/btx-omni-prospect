# Scoring rubric errata preflight

Current resolution: [Rubric v2.0](BTX_Omni_Scoring_Rubric_v2.0.md) is now available. The user corrected A to **86.25 High** at nine days and **88.75 High** at three days; B is **62.00 Moderate**; C is **72.5 B**. These supersede the historical preflight discussion below. The original DOCX remains unchanged. No expected failure is acceptable for the amended targets.

Status: provisional review on 2026-09-20. The authoritative BTX Omni Scoring
Rubric v2.0 document was not found in this checkout. The only scoring DOCX is
`docs/scoring/BTX_Account_Scoring_Working_Draft (1).docx`; it describes an older
proposal and proportional reweighting. It must not substitute for v2.0.
The following compares the task's explicit errata against current code.

## A Signal Confidence

The requested 85.75 at nine days is inconsistent with the requested 88.75 at
three days when only freshness changes. Current contributions are source 30,
entity 25, specificity 20, single independent origin 3.75, freshness 7.5 at
nine days. Total: **86.25 High**, not 85.75. At three days freshness contributes
10 and the total is **88.75 High**. The first quarter is 7.5 elapsed days for
a 30-day window; whole-day ages through seven are within it.

Owners: `modules/scoring/families.py:FAMILIES`,
`modules/scoring/public_rules.py:freshness_points`,
`modules/scoring/public_inputs.py:public_signal_assessment` under
`backend/src/btx_omni/`. The requested nine-day target is a strict expected
failure in `backend/tests/test_sample_enhancement_preflight.py`.
An additional half-point deduction cannot be justified from age alone.

## B Overall customer risk

`0.60 * 52.5 + 0.40 * 76.25 = 31.50 + 30.50 = 62.00`.
`modules/scoring/families.py:overall_customer_risk` computes **62.00**, zero
uplift, no floors, when both inputs are available and public risk is confirmed.
The task's 62 Moderate interpretation is consistent with its supplied band;
the rollup function itself returns no band field. The claimed 61.85 example
cannot be checked in the missing authoritative document.

## C Delivery Feasibility

The current code reproduces **72.50** from these raw observations:

| Factor | Raw observation | Points | Weighted contribution |
|---|---|---:|---:|
| Capability | One funded dated noncritical gap | 75 | 22.50 |
| Schedule | 110 net available hours / 100 required | 75 | 18.75 |
| Material | Most constrained critical material 14 days early | 75 | 11.25 |
| Quality | Valid certification, buyer qualification scheduled | 75 | 11.25 |
| Margin | Quote 100, estimated total cost 90 | 50 | 5.00 |
| Coordination | One date unknown | 75 | 3.75 |

Owner: `modules/scoring/pursuit_inputs.py:factor_points`; aggregation:
`modules/scoring/families.py:assess`. The task calls this grade B. This probe
checks raw bins and exact arithmetic; it does not claim an end-to-end eligible
deal or validate the missing rubric's complete grade table. The old individual
contributions 24, 13.5 and 4 are unavailable from the corresponding discrete bins.

## Executive deck

Per the task, slide 15's Action Priority weights and inverse-resilience risk
formula are non-authoritative. No executive deck was found in the checkout.
Current code uses triage classes in `modules/scoring/action_priority.py` and
direct risk factors in `modules/scoring/internal_risk.py`.
