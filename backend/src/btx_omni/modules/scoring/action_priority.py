"""Rubric v2 section 13: an ordered queue, never a blended action score."""
from decimal import Decimal, InvalidOperation

VERSION = 'BTX_ACTION_PRIORITY_V2'
EXCLUDED = {'COMPLETED', 'CANCELED', 'DISMISSED', 'SNOOZED', 'DUPLICATE', 'INVALID'}


def priority_class(*, confirmed_block: bool = False, disposition: str | None = None) -> int:
    return 0 if confirmed_block else 1 if disposition == 'ESCALATE_NOW' else 2 if disposition == 'VALIDATE_IMMEDIATELY' else 3


def _number(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and 0 <= number <= 100 else None
    except InvalidOperation:
        return None


def action_sort_key(item: dict) -> tuple:
    decision = item.get('underlying_decision') or {}
    score = _number(decision.get('score'))
    ceiling = _number((decision.get('score_range') or {}).get('high'))
    return (priority_class(confirmed_block=item.get('confirmed_block') is True, disposition=decision.get('disposition')),
            0 if score is not None else 1, -(score if score is not None else ceiling if ceiling is not None else Decimal(100)),
            str(item.get('due_date') or '9999-12-31'), str(item.get('created_at') or '9999-12-31'), str(item['id']))


def rank_actions(items: list[dict]) -> list[dict]:
    eligible = [item for item in items if item.get('status') not in EXCLUDED and item.get('valid', True)]
    seen = set()
    result = []
    for item in sorted(eligible, key=action_sort_key):
        identity = item.get('deduplication_key', item['id'])
        if identity in seen:
            continue
        seen.add(identity)
        result.append({**item, 'priority_rank': len(result) + 1, 'priority_class': action_sort_key(item)[0], 'priority_configuration_version': VERSION})
    return result
