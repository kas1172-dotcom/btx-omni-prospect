"""Evidence-linked raw pursuit observations mapped to rubric v2 bins.

The existing commercial payload owns these optional observations. No model or
caller supplies points, weights, or a replacement scoring policy.
"""
from decimal import Decimal, InvalidOperation

from btx_omni.core.clock import evidence_state
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.scoring.families import FAMILIES, FactorInput

_BINS = {
    'buyer_access': {'DECISION_AUTHORITY_TWO_WAY': 100, 'EVALUATION_COMMITTEE_TWO_WAY': 75, 'NAMED_INFLUENCER': 50, 'VERIFIED_ROLE_NO_INTERACTION': 25, 'CONFIRMED_UNREACHABLE': 0},
    'competitive_position': {'BUYER_DOCUMENTED_SOLE_SOURCE': 100, 'ELIGIBLE_INCUMBENT': 75, 'INVITED_BIDDER': 50, 'UNSOLICITED_CHALLENGER': 25, 'EXCLUDED': 0},
    'budget_process': {'BUDGET_DATE_PROCESS_CONFIRMED': 100, 'BUDGET_DATE_CONFIRMED': 75, 'BUDGET_CONFIRMED': 50, 'CONDITIONAL_BUDGET': 25, 'CONFIRMED_NO_FUNDING': 0},
    'track_record': {'TWO_ACCEPTED_SAME_REQUIREMENTS': 100, 'ONE_ACCEPTED_SAME_REQUIREMENTS': 75, 'ACCEPTED_ADJACENT_FAMILY': 50, 'VALIDATED_PROTOTYPE': 25, 'CONFIRMED_NONE': 0},
    'capability_match': {'ALL_AVAILABLE': 100, 'ONE_FUNDED_DATED_NONCRITICAL_GAP': 75, 'MULTIPLE_FUNDED_DATED_NONCRITICAL_GAPS': 50, 'UNFUNDED_REMEDY': 25, 'UNAVAILABLE_BY_NEED': 0},
    'quality_certification': {'VALID_THROUGH_DELIVERY_BUYER_APPROVED': 100, 'VALID_BUYER_QUALIFICATION_SCHEDULED': 75, 'RENEWAL_DATED_OWNER': 50, 'UNDATED_PLAN': 25, 'MANDATORY_UNAVAILABLE_BY_START': 0},
    'coordination': {'ALL_OWNERS_AND_DATES': 100, 'ONE_DATE_UNKNOWN': 75, 'ONE_OWNER_UNKNOWN': 50, 'MULTIPLE_OWNERS_UNKNOWN': 25, 'CONFLICTING_COMMITMENTS': 0},
}


def _number(row, key):
    value = row.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def factor_points(key: str, raw: dict) -> Decimal | None:
    """All numerical thresholds come from the normative v2 factor tables."""
    if key in _BINS:
        value = _BINS[key].get(raw.get('state'))
        return Decimal(value) if value is not None else None
    if key == 'requirement_fit':
        met, total = _number(raw, 'noncritical_met'), _number(raw, 'noncritical_total')
        return met * 100 / total if met is not None and total is not None and 0 <= met <= total and total > 0 else None
    if key == 'price_competitiveness':
        quoted, target = _number(raw, 'quoted_minor'), _number(raw, 'buyer_target_minor')
        if quoted is None or target is None or quoted < 0 or target <= 0:
            return None
        ratio = quoted / target
        return Decimal(100 if ratio <= Decimal('.95') else 75 if ratio <= 1 else 50 if ratio <= Decimal('1.10') else 25 if ratio <= Decimal('1.25') else 0)
    if key == 'schedule_feasibility':
        available, required = _number(raw, 'net_available_hours'), _number(raw, 'required_hours')
        if available is None or required is None or available < 0 or required <= 0:
            return None
        ratio = available / required
        return Decimal(100 if ratio >= Decimal('1.25') else 75 if ratio >= Decimal('1.10') else 50 if ratio >= 1 else 25 if ratio >= Decimal('.90') else 0)
    if key == 'material_readiness':
        days = _number(raw, 'most_constrained_critical_material_days_early')
        return None if days is None else Decimal(100 if days >= 30 else 75 if days >= 14 else 50 if days >= 1 else 25 if days == 0 else 0)
    if key == 'margin':
        quoted, cost = _number(raw, 'quoted_minor'), _number(raw, 'estimated_total_cost_minor')
        if quoted is None or cost is None or quoted <= 0 or cost < 0:
            return None
        margin = (quoted - cost) / quoted
        return Decimal(100 if margin >= Decimal('.30') else 75 if margin >= Decimal('.20') else 50 if margin >= Decimal('.10') else 25 if margin >= 0 else 0)
    return None


def pursuit_inputs(account: dict, opportunity: dict, family: str) -> tuple[dict, tuple[str, ...], tuple[str, ...]]:
    """Read scoped reviewed evidence, retaining unknown critical checks separately."""
    records = opportunity.get('scoring_inputs', {}).get(family, {})
    inputs, blocks, missing = {}, [], []
    for key, _ in FAMILIES[family].weights:
        raw = records.get(key, {})
        ids = tuple(raw.get('evidence_ids', ()))
        scoped = raw.get('opportunity_id') == opportunity['opportunity_id']
        if family == 'delivery_feasibility':
            scoped = scoped and bool(opportunity.get('delivery_facility_id')) and raw.get('facility_id') == opportunity['delivery_facility_id']
        try:
            current = evidence_state(raw.get('reviewed_as_of'), as_of=account['as_of'], window_days=2 if family == 'delivery_feasibility' else 30) == 'CURRENT'
        except (ValueError, TypeError):
            current = False
        resolved = [resolve_commercial_evidence(account, eid) for eid in ids]
        def related(item):
            if not item:
                return False
            record = item['record']
            return (item['record_id'] == opportunity['opportunity_id']
                    or record.get('opportunity_id') == opportunity['opportunity_id']
                    or opportunity['opportunity_id'] in record.get('related_record_ids', [])
                    or (record.get('component_id') == opportunity['component_id']
                        and record.get('quote_revision_id') == opportunity['quote_revision_id']))
        valid = scoped and current and bool(ids) and all(related(item) for item in resolved)
        points = factor_points(key, raw) if valid else None
        if key == 'requirement_fit':
            if valid and raw.get('critical_requirements_pass') is False:
                blocks.append('A mandatory technical requirement fails.')
            elif not valid or raw.get('critical_requirements_pass') is not True:
                missing.append('Confirm every critical technical requirement before scoring the pursuit.')
        if family == 'delivery_feasibility' and valid:
            if raw.get('state') in {'UNAVAILABLE_BY_NEED', 'MANDATORY_UNAVAILABLE_BY_START', 'CONFLICTING_COMMITMENTS'}:
                blocks.append('A required delivery capability, qualification or site commitment is unavailable.')
            if key == 'schedule_feasibility' and points == 0:
                blocks.append('Capacity mitigation is required before committing the work.')
            if key == 'material_readiness' and points == 0:
                blocks.append('A critical material is late; confirm an approved substitute or revised plan.')
        inputs[key] = FactorInput(points, ids if valid else (),
            f"{key.replace('_', ' ').capitalize()}: reviewed evidence for this pursuit." if points is not None else f"{key.replace('_', ' ').capitalize()}: current, linked pursuit evidence is still required.",
            raw_value=str({k: v for k, v in raw.items() if k not in {'evidence_ids', 'opportunity_id'}}) if valid else None,
            period=account['as_of'])
    return inputs, tuple(blocks), tuple(missing)
