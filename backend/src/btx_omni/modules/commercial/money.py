"""Explicit presentation of canonical integer money; no currency conversion."""
from decimal import Decimal


def model_money_projection(value, *, currency: str):
    """Present qualified USD minor units without asking a model to scale them.

    Persisted/API records are unchanged. Unknown currencies have no invented
    exponent or major-unit display. Null remains unknown, never zero.
    """
    if isinstance(value, dict):
        scoped_currency = value.get('currency', currency)
        result = {}
        for key, child in value.items():
            if key.endswith('_minor') and (child is None or type(child) is int):
                result[key.removesuffix('_minor') + '_money'] = (
                    None if child is None else
                    {'currency': scoped_currency, 'major_units': format(Decimal(child) / 100, '.2f'),
                     'display': f'{scoped_currency} {Decimal(child) / 100:,.2f}'}
                    if scoped_currency == 'USD' else
                    {'currency': scoped_currency, 'minor_units': child, 'major_units': None,
                     'limitation': 'Currency exponent is not qualified; do not render as major units.'}
                )
            else:
                result[key] = model_money_projection(child, currency=scoped_currency)
        return result
    if isinstance(value, (tuple, list)):
        return [model_money_projection(child, currency=currency) for child in value]
    return value
