"""Commercial decision inputs from canonical transactions, never scenario scores."""
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from btx_omni.domain.work import Action
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.scoring.account_attractiveness import (
    FACTORS,
    seller_attractiveness_projection,
)
from btx_omni.modules.scoring.commercial_inputs import commercial_attractiveness_inputs
from btx_omni.modules.scoring.families import FactorInput, assess


def _clamp(value: Decimal) -> Decimal:
    return max(Decimal(0), min(Decimal(100), value))


def _money(value: int | None, currency: str) -> str:
    return "unknown" if value is None else f"{currency} {Decimal(value) / 100:,.2f}"


def customer_decisions(account: dict, *, account_id: str, revision: str, current_customer: bool, work_items: tuple[Action, ...] = ()) -> dict:
    as_of = date.fromisoformat(account["as_of"])
    months = sorted(account["monthly_commercial_history"], key=lambda r: r["period"])
    state = fulfillment_state(account, canonical_account_id=account_id, revision=revision)
    health, risk = {}, {}

    def factor(key, health_points, risk_points, evidence, reason, required, observed, *, risk_required=None):
        common = {"evidence_ids": tuple(sorted(set(evidence))), "reason": reason, "period": account["as_of"],
                  "required_fields": tuple(required), "observed_fields": tuple(observed)}
        health[key] = FactorInput(health_points, **common)
        risk[key] = FactorInput(risk_points, **{**common, "required_fields": tuple(risk_required or required)})

    recent = sum(r["bookings_minor"] for r in months[-3:])
    previous = sum(r["bookings_minor"] for r in months[-6:-3])
    change = Decimal(recent - previous) / previous if len(months) >= 6 and previous > 0 else None
    factor("commercial_momentum", _clamp(50 + 100 * change) if change is not None else None,
           _clamp(-200 * change) if change is not None else None,
           [r["snapshot_id"] for r in months[-6:]],
           f"Latest three recorded months booked {_money(recent, account['currency'])} versus {_money(previous, account['currency'])} in the preceding three. This is not a prior-year comparison.",
           ("recent_three_month_bookings", "preceding_three_month_bookings"),
           ("recent_three_month_bookings", "preceding_three_month_bookings") if len(months) >= 6 else (),
           risk_required=("recent_three_month_bookings", "preceding_three_month_bookings", "prior_ttm_bookings", "prior_ttm_revenue"))

    revisions = {r["quote_revision_id"]: r for r in account["quote_revisions"]}
    closed = [q for q in account["quotes"] if q.get("status") in {"WON", "LOST"} and q.get("current_revision_id") in revisions]
    total = sum(revisions[q["current_revision_id"]]["total_minor"] for q in closed)
    won = sum(revisions[q["current_revision_id"]]["total_minor"] for q in closed if q["status"] == "WON")
    conversion = Decimal(won) * 100 / total if total else None
    factor("pipeline", conversion, 100 - conversion if conversion is not None else None,
           [q["quote_id"] for q in closed], f"Historical closed-quote value: {_money(won, account['currency'])} won out of {_money(total, account['currency'])}. Open and expired quotes are not assumed losses; this is not PWIN.",
           ("closed_quote_values", "won_quote_values", "future_booking_target"),
           ("closed_quote_values", "won_quote_values") if closed else ())

    source_lines = {r["order_line_id"]: r for r in account["order_lines"]}
    open_value = sum(r["remaining_quantity"] * source_lines[r["order_line_id"]]["unit_price_minor"] for r in state["lines"])
    late_value = sum(r["remaining_quantity"] * source_lines[r["order_line_id"]]["unit_price_minor"] for r in state["lines"] if r["overdue"])
    late_share = Decimal(late_value) * 100 / open_value if open_value else None
    factor("backlog", 100 - late_share if late_share is not None else None, late_share,
           [r["order_line_id"] for r in state["lines"] if r["remaining_quantity"]],
           f"{_money(late_value, account['currency'])} of {_money(open_value, account['currency'])} of open firm value is past commitment. No open balance is not proof of future demand.",
           ("open_firm_value", "overdue_firm_value", "future_contract_coverage"),
           ("open_firm_value", "overdue_firm_value"))

    interactions = [r for r in account["interactions"] if r.get("date") and date.fromisoformat(r["date"]) <= as_of]
    last = max(interactions, key=lambda r: (r["date"], r["interaction_id"]), default=None)
    age = (as_of - date.fromisoformat(last["date"])).days if last else None
    engagement = Decimal(100 if age <= 14 else 70 if age <= 30 else 40 if age <= 60 else 10) if age is not None else None
    factor("engagement", engagement, 100 - engagement if engagement is not None else None,
           [last["interaction_id"]] if last else [],
           f"Latest role-based interaction is {age} days before the demo as-of date." if last else "No dated interaction is available.",
           ("dated_interaction", "verified_functional_person_coverage", "accountable_user_owner"),
           ("dated_interaction",) if last else ())

    by_program = defaultdict(int)
    revenues = [r for r in account["revenue_events"] if date.fromisoformat(r["recognized_date"]) <= as_of]
    for record in revenues:
        by_program[source_lines[record["order_line_id"]]["program_id"]] += record["revenue_minor"]
    total_revenue = sum(by_program.values())
    concentration = Decimal(max(by_program.values())) * 100 / total_revenue if total_revenue else None
    factor("concentration", 100 - concentration if concentration is not None else None, concentration,
           [r["revenue_event_id"] for r in revenues],
           f"Largest program accounts for {concentration.quantize(Decimal('.01'))}% of this account's recorded recognized revenue." if concentration is not None else "No recognized revenue denominator is available.",
           ("recognized_revenue", "program_identity"), ("recognized_revenue", "program_identity") if revenues else ())

    paid = defaultdict(int)
    for payment in account["payments"]:
        if date.fromisoformat(payment["paid_date"]) <= as_of:
            paid[payment["invoice_id"]] += payment["amount_minor"]
    invoices = [r for r in account["invoices"] if date.fromisoformat(r["invoice_date"]) <= as_of]
    outstanding = sum(r["amount_minor"] - paid[r["invoice_id"]] for r in invoices)
    dates_known = all(r.get("due_date") for r in invoices)
    overdue = sum(r["amount_minor"] - paid[r["invoice_id"]] for r in invoices if r.get("due_date") and date.fromisoformat(r["due_date"]) < as_of)
    friction = Decimal(overdue) * 100 / outstanding if outstanding and dates_known else Decimal(0) if invoices and outstanding == 0 else None
    factor("friction", 100 - friction if friction is not None else None, friction,
           [r["invoice_id"] for r in invoices],
           f"{_money(overdue, account['currency'])} is past due out of {_money(outstanding, account['currency'])} currently outstanding. Credit limits and quantified quality exposure remain unknown.",
           ("invoice_balance", "due_dates", "credit_limit", "quality_exposure"),
           (("invoice_balance",) if invoices else ()) + (("due_dates",) if invoices and dates_known else ()))
    return {
        "customer_health": assess("customer_health", subject_id=account_id, as_of=account["as_of"], revision=revision,
                                  inputs=health, eligible=current_customer, eligibility_reasons=() if current_customer else ("Customer Health is not applicable to a net-new prospect.",)),
        "internal_commercial_risk": assess("internal_commercial_risk", subject_id=account_id, as_of=account["as_of"], revision=revision,
                                           inputs=risk, eligible=current_customer, eligibility_reasons=() if current_customer else ("No current customer relationship is established.",)),
        "fulfillment_constraints": state["constraints"],
        "opportunities": opportunity_decisions(account, account_id=account_id, revision=revision),
        "action_priorities": action_decisions(account, account_id=account_id, revision=revision, fulfillment=state, work_items=work_items),
    }


def opportunity_decisions(account: dict, *, account_id: str, revision: str) -> list[dict]:
    """Opportunity scope is not the account's aggregate score or generic fit fixture."""
    results = []
    for opportunity in account["opportunities"]:
        cid = opportunity["component_id"]
        lines = [line for line in account["order_lines"] if line["component_id"] == cid]
        lids = {line["order_line_id"] for line in lines}
        scoped = {**account, "order_lines": lines,
                  "revenue_events": [r for r in account["revenue_events"] if r["order_line_id"] in lids],
                  "shipments": [r for r in account["shipments"] if r["order_line_id"] in lids],
                  "cancellations": [r for r in account["cancellations"] if r["order_line_id"] in lids]}
        inputs = commercial_attractiveness_inputs(scoped)
        projection = seller_attractiveness_projection(inputs, calculated_at=datetime.combine(date.fromisoformat(account["as_of"]), datetime.min.time(), UTC))
        factors = {}
        for definition, factor_result in zip(FACTORS, projection.factors, strict=True):
            required = tuple(f"{definition.key}.{s.rubric.key}" for s in definition.subfactors) or (definition.key,)
            observed = tuple(key for key in required if key in inputs.selections)
            factors[definition.key] = FactorInput(factor_result.factor_score, factor_result.evidence_ids,
                                                  "Component-scoped accepted work supports only the listed observed inputs; missing specification and public program evidence remain unknown.",
                                                  required_fields=required, observed_fields=observed)
        priority = assess("opportunity_priority", subject_id=opportunity["opportunity_id"], as_of=account["as_of"], revision=revision,
                          inputs=factors, eligible=True)
        buyer = opportunity.get("qualified_buyer_contact_id")
        buyer_evidence = [r for r in account["interactions"] if r["interaction_id"] in opportunity.get("buyer_qualification_evidence_ids", [])
                          and buyer in r.get("real_person_ids", []) and opportunity["opportunity_id"] in r.get("related_record_ids", [])]
        specified_lines = [r for r in account["quote_lines"] if r["quote_revision_id"] == opportunity["quote_revision_id"]
                           and r["component_id"] == cid and r.get("technical_requirements")]
        pursuit_qualified = bool(buyer and buyer_evidence and specified_lines and opportunity["stage"] in {"QUALIFIED", "NEGOTIATION", "PROPOSAL_APPROVED"})
        pwin_inputs = {
            "buyer_commitment": FactorInput(None, (opportunity["opportunity_id"],), "A role target or published contact is not a qualified buyer with decision authority.", required_fields=("qualified_buyer", "decision_authority", "confirmed_need")),
            "solution_fit": FactorInput(None, (cid,), "Production-ready technical scope and qualification are not supplied.", required_fields=("technical_specification", "scoped_qualification")),
            "commercial_position": FactorInput(None, (opportunity["quote_revision_id"],), "A quoted value is known; approved economics and the buyer's commercial position are not established.", raw_value=opportunity["value_minor"], required_fields=("quoted_value", "approved_economics", "buyer_position"), observed_fields=("quoted_value",)),
            "competitive_position": FactorInput(None, (), "No verified competitive assessment is attached.", required_fields=("competition_assessment",)),
            "decision_timing": FactorInput(None, (opportunity["opportunity_id"],), "Expected close is a scenario planning date, not a buyer-confirmed decision date.", raw_value=opportunity.get("expected_close_date"), required_fields=("expected_close", "confirmed_decision_date"), observed_fields=("expected_close",) if opportunity.get("expected_close_date") else ()),
        }
        pwin = assess("pwin", subject_id=opportunity["opportunity_id"], as_of=account["as_of"], revision=revision, inputs=pwin_inputs,
                      eligible=pursuit_qualified, eligibility_reasons=() if pursuit_qualified else ("The supplied pursuit has not established a qualified stage, evidenced buyer and production-ready specification.",))
        delivery = assess("delivery_feasibility", subject_id=opportunity["opportunity_id"], as_of=account["as_of"], revision=revision,
                          inputs={key: FactorInput(None, (cid,), reason, required_fields=required) for key, reason, required in (
                              ("qualification", "Facility capability is not part/program qualification.", ("technical_specification", "facility_scoped_approval")),
                              ("capacity", "No current capacity reservation is established.", ("required_quantity", "required_date", "capacity_confirmation")),
                              ("materials", "Material specification and availability are unknown.", ("material_specification", "material_availability")),
                              ("logistics", "Proximity does not establish a deliverable schedule.", ("verified_destination", "delivery_plan")),
                          )}, eligible=bool(specified_lines), eligibility_reasons=() if specified_lines else ("This component opportunity has no scoped production-ready technical requirements.",))
        results.append({"opportunity_id": opportunity["opportunity_id"], "account_id": account_id, "component_id": cid,
                        "value_minor": opportunity["value_minor"], "currency": account["currency"], "stage": opportunity["stage"],
                        "qualification_status": "QUALIFIED_PURSUIT" if pursuit_qualified else "NEEDS_TECHNICAL_AND_BUYER_REVIEW", "durability_status": "FUTURE_PRODUCTION_HORIZON_UNESTABLISHED",
                        "recommendation_eligible": pursuit_qualified and priority["score"] is not None and delivery["score"] is not None,
                        "opportunity_priority": priority, "pwin": pwin, "delivery_feasibility": delivery})
    return results


def action_decisions(account: dict, *, account_id: str, revision: str, fulfillment: dict, work_items: tuple[Action, ...] = ()) -> list[dict]:
    states = {r["order_line_id"]: r for r in fulfillment["lines"]}
    source_lines = {r["order_line_id"]: r for r in account["order_lines"]}
    results = []
    for action in account["actions"]:
        evidence = action.get("evidence_record_ids", [])
        resolved = [resolve_commercial_evidence(account, eid) for eid in evidence]
        exposures = []
        for record in resolved:
            if record and record["kind"] == "order_lines":
                lid = record["record_id"]
                exposures.append(states[lid]["remaining_quantity"] * source_lines[lid]["unit_price_minor"])
            elif record and record["kind"] == "opportunities":
                exposures.append(record["record"]["value_minor"])
        exposure = max(exposures, default=None)  # avoid summing overlapping commercial hypotheses
        revenue = account["ttm_summary"]["revenue_minor"]
        impact = _clamp(Decimal(exposure) * 1000 / revenue) if exposure is not None and revenue > 0 else None
        due = date.fromisoformat(action["due_date"]) if action.get("due_date") else None
        days = (due - date.fromisoformat(account["as_of"])).days if due else None
        urgency = Decimal(100 if days < 0 else 80 if days <= 7 else 60 if days <= 14 else 40 if days <= 30 else 20) if days is not None else None
        scoped = bool(evidence) and all(resolved)
        linked = [item for item in work_items if item.account_id == account_id and ("commercial_action", action["action_id"]) in item.context_referents]
        work = linked[0] if len(linked) == 1 else None
        assigned = bool(work and work.owner_id)
        terminal = bool(work and work.status.value in {"COMPLETED", "CANCELED"})
        inputs = {
            "impact": FactorInput(impact, tuple(evidence), f"Largest linked open-order or quoted-opportunity exposure is {_money(exposure, account['currency'])}; it is not expected loss or recognized revenue.", raw_value=exposure, required_fields=("linked_exposure", "account_revenue_denominator"), observed_fields=(("linked_exposure",) if exposure is not None else ()) + (("account_revenue_denominator",) if revenue > 0 else ())),
            "urgency": FactorInput(urgency, (action["action_id"],), f"The case follow-up is due {action.get('due_date')}; {days} days from the demo as-of date.", raw_value=days, required_fields=("due_date",), observed_fields=("due_date",) if due else ()),
            "readiness": FactorInput(Decimal(100) if assigned and scoped else None, tuple(evidence) + ((work.id,) if work else ()), "The Action has an assigned user; approval and current version checks still control execution." if assigned else "A role target is not an assigned user; create or reconcile an authorized Action before execution.", required_fields=("scoped_evidence", "assigned_user"), observed_fields=(("scoped_evidence",) if scoped else ()) + (("assigned_user",) if assigned else ())),
            "scope": FactorInput(Decimal(100) if scoped else None, tuple(evidence), "Referenced records resolve in the selected canonical account." if scoped else "One or more source references require resolution.", required_fields=("account_scope", "resolved_record_references"), observed_fields=("account_scope", "resolved_record_references") if scoped else ()),
        }
        work_revision = revision + ":work:" + ";".join(f"{item.id}@{item.version}" for item in sorted(linked, key=lambda item: item.id))
        decision = assess("action_priority", subject_id=action["action_id"], as_of=account["as_of"], revision=work_revision, inputs=inputs,
                          eligible=scoped and not terminal and len(linked) <= 1,
                          eligibility_reasons=("Linked work is terminal; do not recreate it automatically.",) if terminal else ("Resolve duplicate work mappings.",) if len(linked) > 1 else () if scoped else ("Resolve all action evidence in the account scope.",))
        results.append({"action_id": action["action_id"], "account_id": account_id, "title": action["title"],
                        "decision": decision, "work_status": "AMBIGUOUS_MAPPING" if len(linked) > 1 else work.status.value if work else "SOURCE_CASE_FOLLOW_UP_NOT_CREATED_WORK",
                        "linked_work_ids": [item.id for item in linked],
                        "execution_requirements": ["Resolve an accountable user", "Create or reconcile the local Action proposal", "Apply current approval/version checks"],
                        "evidence_ids": evidence})
    return results
