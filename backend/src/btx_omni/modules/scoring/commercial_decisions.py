"""Commercial decision inputs from canonical transactions, never scenario scores."""
from datetime import UTC, date, datetime

from btx_omni.domain.work import Action
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.scoring.account_attractiveness import (
    FACTORS,
    seller_attractiveness_projection,
)
from btx_omni.modules.scoring.action_priority import VERSION as ACTION_PRIORITY_VERSION
from btx_omni.modules.scoring.action_priority import rank_actions
from btx_omni.modules.scoring.commercial_inputs import commercial_attractiveness_inputs
from btx_omni.modules.scoring.customer_health import health_inputs
from btx_omni.modules.scoring.families import FactorInput, assess
from btx_omni.modules.scoring.internal_risk import risk_inputs
from btx_omni.modules.scoring.opportunity_gates import opportunity_gates
from btx_omni.modules.scoring.pursuit_inputs import pursuit_inputs


def customer_decisions(account: dict, *, account_id: str, revision: str, current_customer: bool, work_items: tuple[Action, ...] = (), facility_ids: frozenset[str] = frozenset()) -> dict:
    state = fulfillment_state(account, canonical_account_id=account_id, revision=revision)
    risk = risk_inputs(account, state)
    return {
        "customer_health": assess("customer_health", subject_id=account_id, as_of=account["as_of"], revision=revision,
                                  inputs=health_inputs(account, state), eligible=current_customer, eligibility_reasons=() if current_customer else ("Customer Health is not applicable to a net-new prospect.",)),
        "internal_commercial_risk": assess("internal_commercial_risk", subject_id=account_id, as_of=account["as_of"], revision=revision,
                                           inputs=risk, eligible=current_customer, eligibility_reasons=() if current_customer else ("No current customer relationship is established.",)),
        "fulfillment_constraints": state["constraints"],
        "opportunities": opportunity_decisions(account, account_id=account_id, revision=revision, facility_ids=facility_ids),
        "action_priorities": action_decisions(account, account_id=account_id, revision=revision, fulfillment=state, work_items=work_items),
    }


def opportunity_decisions(account: dict, *, account_id: str, revision: str, facility_ids: frozenset[str] = frozenset()) -> list[dict]:
    """Opportunity scope is not the account's aggregate score or generic fit fixture."""
    results = []
    for opportunity in account["opportunities"]:
        cid = opportunity["component_id"]
        lines = [line for line in account["order_lines"] if line["component_id"] == cid]
        lids = {line["order_line_id"] for line in lines}
        scoped = {**account, "scoring_opportunity_id": opportunity['opportunity_id'],
                  "opportunity_score_observations": opportunity.get('score_observations', []), "order_lines": lines,
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
                                                  required_fields=required, observed_fields=observed,
                                                  lower_bound=factor_result.score_low if factor_result.factor_score is None and factor_result.evidence_ids else None,
                                                  upper_bound=factor_result.score_high if factor_result.factor_score is None and factor_result.evidence_ids else None)
        priority = assess("opportunity_priority", subject_id=opportunity["opportunity_id"], as_of=account["as_of"], revision=revision,
                          inputs=factors, eligible=True)
        gates = opportunity_gates(account, opportunity, inputs, priority)
        buyer = opportunity.get("qualified_buyer_contact_id")
        buyer_evidence = [r for r in account["interactions"] if r["interaction_id"] in opportunity.get("buyer_qualification_evidence_ids", [])
                          and buyer in r.get("real_person_ids", []) and opportunity["opportunity_id"] in r.get("related_record_ids", [])]
        specified_lines = [r for r in account["quote_lines"] if r["quote_revision_id"] == opportunity["quote_revision_id"]
                           and r["component_id"] == cid and r.get("technical_requirements")]
        pursuit_qualified = bool(gates['qualified'] == 'YES' and buyer and buyer_evidence and specified_lines and opportunity["stage"] in {"QUALIFIED", "NEGOTIATION", "PROPOSAL_APPROVED"})
        pwin_inputs, pwin_blocks, pwin_missing = pursuit_inputs(account, opportunity, 'pwin')
        pwin = assess('pwin', subject_id=opportunity['opportunity_id'], as_of=account['as_of'], revision=revision,
                      inputs=pwin_inputs, eligible=pursuit_qualified and not pwin_missing,
                      eligibility_reasons=pwin_missing + (() if pursuit_qualified else ('Establish a qualified buyer, confirmed need and scoped specification.',)),
                      blocking_constraints=pwin_blocks)
        delivery_inputs, delivery_blocks, delivery_missing = pursuit_inputs(account, opportunity, 'delivery_feasibility')
        facility = opportunity.get('delivery_facility_id')
        facility_known = facility in facility_ids
        delivery = assess('delivery_feasibility', subject_id=opportunity['opportunity_id'], as_of=account['as_of'], revision=revision,
                          inputs=delivery_inputs, eligible=bool(specified_lines and facility_known),
                          eligibility_reasons=delivery_missing + (() if specified_lines and facility_known else ('Confirm a named facility and scoped production requirements.',)),
                          blocking_constraints=delivery_blocks)
        results.append({"opportunity_id": opportunity["opportunity_id"], "account_id": account_id, "component_id": cid,
                        "value_minor": opportunity["value_minor"], "currency": account["currency"], "stage": opportunity["stage"],
                        "qualification_status": gates['qualified'], "durability_status": gates['durable'], 'gates': gates,
                        "recommendation_eligible": pursuit_qualified and priority["score"] is not None and delivery["score"] is not None,
                        "attractiveness": {"score": projection.score, "score_range": projection.score_range,
                                           "configuration_version": projection.configuration_version,
                                           "coverage": projection.coverage, "missingness": projection.missingness,
                                           "subject_id": opportunity["opportunity_id"]},
                        "opportunity_priority": priority, "pwin": pwin, "delivery_feasibility": delivery})
    return results


def action_decisions(account: dict, *, account_id: str, revision: str, fulfillment: dict, work_items: tuple[Action, ...] = ()) -> list[dict]:
    opportunities = {item['opportunity_id']: item for item in opportunity_decisions(account, account_id=account_id, revision=revision)}
    risk = assess('internal_commercial_risk', subject_id=account_id, as_of=account['as_of'], revision=revision,
                  inputs=risk_inputs(account, fulfillment), eligible=True)
    rows = []
    for action in account['actions']:
        evidence = action.get('evidence_record_ids', [])
        resolved = [resolve_commercial_evidence(account, eid) for eid in evidence]
        linked = [item for item in work_items if item.account_id == account_id and ('commercial_action', action['action_id']) in item.context_referents]
        work = linked[0] if len(linked) == 1 else None
        status = work.status.value if work else action.get('status', 'OPEN')
        valid = bool(evidence) and all(resolved) and len(linked) <= 1
        underlying = {}
        for item in resolved:
            if item and item['kind'] == 'opportunities':
                underlying = opportunities[item['record_id']]['opportunity_priority']
                break
            if item and item['kind'] in {'service_events', 'invoices', 'order_lines'}:
                underlying = risk
        confirmed_block = any(item and item['kind'] == 'service_events'
            and item['record'].get('confirmed') is True
            and item['record'].get('issue_type') in {'SAFETY_SHUTDOWN', 'LEGAL_PROHIBITION', 'STOPPED_SHIPMENT'}
            for item in resolved)
        public = account.get('public_event_assessments', {}).get(action.get('underlying_event_id'))
        if public and public.get('as_of') == account['as_of'] and public.get('family') == 'risk_severity':
            underlying = public
        rows.append({'id': action['action_id'], 'action_id': action['action_id'], 'account_id': account_id,
            'title': action['title'], 'status': status, 'valid': valid,
            'due_date': work.due_date if work else action.get('due_date'),
            'created_at': work.created_at if work else action.get('created_at'),
            'confirmed_block': confirmed_block, 'underlying_decision': underlying,
            'work_status': status if work else 'SOURCE_CASE_FOLLOW_UP_NOT_CREATED_WORK',
            'linked_work_ids': [item.id for item in linked], 'evidence_ids': evidence,
            'execution_requirements': ['Confirm ownership and current approval before execution.']})
    results = rank_actions(rows)
    for row in results:
        underlying = row['underlying_decision']
        row['decision'] = {
            'decision_id': f"action-order:{revision}:{row['action_id']}:{row['priority_rank']}",
            'family': 'action_priority', 'subject_id': row['action_id'], 'as_of': account['as_of'], 'revision': revision,
            'configuration_version': ACTION_PRIORITY_VERSION, 'score': None, 'status': 'RANKED',
            'priority_rank': row['priority_rank'], 'priority_class': row['priority_class'],
            'underlying_decision_id': underlying.get('decision_id'), 'factors': [],
            'eligibility_reasons': (), 'blocking_constraints': (),
            'data_coverage': underlying.get('data_coverage', {'present': 0, 'applicable': 1, 'ratio': 0, 'missing_fields': ['underlying_assessment']}),
            'interpretation': 'Ranked by confirmed mandatory issue, risk disposition, assessment completeness, underlying score, due date and stable identity. This is not a separate numeric score.',
        }
    return results
