"""Account-level map facets from canonical records, never inferred site capacity."""
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.persistence.commercial_import import BU_CROSSWALK


def map_commercial_context(ledger: dict | None, *, canonical_account_id: str | None = None, revision: str = '') -> dict:
    if ledger is None:
        return {"naics_assignments": [], "commercial_business_unit_ids": [], "commercial_context_scope": "UNAVAILABLE"}
    business_units = sorted({BU_CROSSWALK[row["business_unit_id"]]
                             for row in ledger.get("components", [])
                             if row.get("business_unit_id") in BU_CROSSWALK})
    attention = None
    if canonical_account_id and 'order_lines' in ledger:
        state = fulfillment_state(ledger, canonical_account_id=canonical_account_id, revision=revision)
        states = set()
        relevant = set()
        for line in state['lines']:
            if line['overdue']:
                states.add('MISSED_COMMITMENT')
            if line['shipped_unaccepted_quantity']:
                states.add('ACCEPTANCE_PENDING')
            if line['remaining_quantity']:
                states.add('OPEN_SHIPMENT')
            if line['overdue'] or line['shipped_unaccepted_quantity'] or line['remaining_quantity']:
                relevant.add(line['order_line_id'])
        if not states and state['lines']:
            states.add('NO_OPEN_FULFILLMENT_EXCEPTION')
        attention = {'states': sorted(states), 'as_of': state['as_of'], 'revision': revision,
                     'order_line_ids': sorted(relevant), 'scope': 'ACCOUNT_COMMERCIAL_HISTORY_NOT_SITE_CAPACITY'}
    return {"naics_assignments": ledger.get("naics_assignments", []),
            "commercial_business_unit_ids": business_units,
            "fulfillment_attention": attention,
            "commercial_context_scope": "ACCOUNT_SCENARIO_NOT_CUSTOMER_SITE_QUALIFICATION"}
