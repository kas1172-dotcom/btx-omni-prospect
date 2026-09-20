"""Normative v2 public-evidence bins; collection cadence is not fact freshness."""
from decimal import Decimal, InvalidOperation

VERSION = 'BTX_PUBLIC_INPUTS_V2'
SOURCE_POINTS = {'TIER_1_AUTHORITATIVE_STRUCTURED': 100, 'TIER_2_AUTHORITATIVE_PUBLISHER': 75,
                 'TIER_3_REPUTABLE_SECONDARY': 50, 'TIER_4_DISCOVERY': 25}
GOVERNMENT_SOURCES = {'sam_gov', 'samgov', 'sam', 'usaspending', 'sec', 'sec_edgar', 'nasa', 'commerce', 'federal_register'}
AWARD_TYPES = {'CONTRACT_AWARD', 'CONTRACT_MODIFICATION', 'SUPPLIER_AWARD', 'CONTRACT_REDUCTION', 'PROGRAM_CANCELLATION', 'GOVERNMENT_FUNDING', 'GRANT_AWARD'}
FACILITY_TYPES = {'FACILITY_EXPANSION', 'CAPACITY_EXPANSION', 'NEW_FACILITY', 'FACILITY_CLOSURE', 'WORKFORCE_REDUCTION'}
FILING_TYPES = {'REGULATORY_APPROVAL', 'REGULATORY_CHANGE', 'FINANCIAL_DISTRESS', 'EXPORT_RESTRICTION', 'EARNINGS_SIGNAL'}


def required_fields(kind):
    if kind in AWARD_TYPES:
        return ('recipient', 'instrument_id', 'action_type', 'amount', 'amount_basis', 'effective_date', 'work_description')
    if kind in FACILITY_TYPES:
        return ('organization', 'site', 'change_type', 'effective_date', 'affected_operation')
    if kind in FILING_TYPES:
        return ('legal_entity', 'record_id', 'event_type', 'report_date', 'affected_scope')
    return ('organization', 'event_type', 'effective_date', 'affected_scope')


def freshness_window_hours(kind):
    return 24 * (30 if kind in AWARD_TYPES | FACILITY_TYPES | FILING_TYPES or kind == 'EXECUTIVE_CHANGE' else 7)


def freshness_points(age_hours, window_hours):
    if age_hours is None or age_hours < 0:
        return None
    return 100 if age_hours <= window_hours / 4 else 75 if age_hours <= window_hours / 2 else 50 if age_hours <= window_hours else 0


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def risk_points(key, facts):
    if key == 'impact':
        kind = facts.get('risk_condition')
        if kind in {'BANKRUPTCY', 'LEGAL_PROHIBITION', 'ENTIRE_PROGRAM_CANCELLATION'}:
            return 100
        if kind == 'FACILITY_CLOSURE':
            return 75
        reduction, delay = number(facts.get('program_reduction_percent')), number(facts.get('delay_days'))
        if reduction is not None and 0 <= reduction <= 100:
            return 75 if reduction >= 25 else 50 if reduction >= 10 else 25 if reduction > 0 else 0
        if delay is not None and delay >= 0:
            return 50 if delay >= 30 else 25 if delay > 0 else 0
        return 0 if kind == 'CONFIRMED_NO_ADVERSE_CHANGE' else None
    if key == 'materiality':
        shares = [number(facts.get(name)) for name in ('affected_revenue_share_percent', 'affected_backlog_share_percent')]
        pursuit = number(facts.get('affected_pursuit_share_percent'))
        share = pursuit if facts.get('subject_kind') == 'PROSPECT' else max(shares) if all(v is not None and 0 <= v <= 100 for v in shares) else None
        return None if share is None or not 0 <= share <= 100 else 100 if share >= 50 else 75 if share >= 25 else 50 if share >= 10 else 25 if share > 0 else 0
    if key == 'imminence':
        days = number(facts.get('days_until_effect'))
        return None if days is None else 100 if days <= 30 else 75 if days <= 90 else 50 if days <= 180 else 25 if days <= 365 else 0
    if key == 'persistence':
        if facts.get('permanent_effect') == 'true':
            return 100
        days = number(facts.get('remaining_effect_days'))
        return None if days is None or days < 0 else 75 if days > 365 else 50 if days >= 91 else 25 if days > 0 else 0
    if key == 'breadth':
        return {'ENTERPRISE': 100, 'MULTIPLE_BUSINESS_UNITS': 75, 'MULTIPLE_SITES_ONE_BU': 50, 'FACILITY': 25, 'PROGRAM': 25, 'ISOLATED_COMPONENT': 0}.get(facts.get('risk_breadth'))
    if key == 'reversibility':
        return {'REMEDY_UNAVAILABLE': 100, 'CONFIRMED_NO_PLAN': 75, 'PLAN_NOT_STARTED': 50, 'UNDERWAY_DATED_MILESTONES': 25, 'FULLY_MITIGATED': 0}.get(facts.get('risk_mitigation'))
    return None


RISK_FIELDS = {
    'impact': ('risk_condition', 'program_reduction_percent', 'delay_days'),
    'materiality': ('affected_revenue_share_percent', 'affected_backlog_share_percent', 'affected_pursuit_share_percent', 'subject_kind'),
    'imminence': ('days_until_effect',), 'persistence': ('permanent_effect', 'remaining_effect_days'),
    'breadth': ('risk_breadth',), 'reversibility': ('risk_mitigation',),
}
