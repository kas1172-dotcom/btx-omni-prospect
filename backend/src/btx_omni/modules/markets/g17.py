"""Deterministic published-number adapter; fixed cells retain interior missingness.

Board download has a quoted native code, year, three separator spaces, then
10-character monthly cells. Header code padding varies: never assume the year
is at one global offset. Empty trailing months are unavailable, not zero.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from btx_omni.modules.markets.registry import BY_CODE

ADAPTER_VERSION = 'BTX_G17_FIXED_MONTHS_1'
_ROW = re.compile(r'^"([^"\r\n]+)" +([0-9]{4})(.*)$')
_HEADER = re.compile(r'^"([^:]+): (.+)"$')


def month_offset(month: date, delta: int) -> date:
    ordinal = month.year * 12 + month.month - 1 + delta
    year, zero_month = divmod(ordinal, 12)
    return date(year, zero_month + 1, 1)


def parse_g17(body: bytes, *, as_of: date, history_months: int = 60) -> dict:
    if not 48 <= history_months <= 120 or not body or len(body) > 5_000_000:
        raise ValueError('G17 source/history budget is invalid.')
    try:
        text = body.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('G17 source is not UTF-8 text.') from None
    earliest = month_offset(as_of.replace(day=1), -history_months)
    headers, observations, rows_seen = {}, {code: {} for code in BY_CODE}, set()
    for line_number, line in enumerate(text.splitlines(), 1):
        header = _HEADER.fullmatch(line)
        if header and header[1] in BY_CODE:
            if header[1] in headers:
                raise ValueError('G17 repeats a selected series header.')
            headers[header[1]] = header[2]
            continue
        row = _ROW.fullmatch(line)
        if row is None:
            if any(line.startswith(f'"{code}"') for code in BY_CODE):
                raise ValueError(f'Malformed selected G17 row at line {line_number}.')
            continue
        code, year_text, tail = row.groups()
        if code not in BY_CODE:
            continue
        key = (code, year_text)
        if key in rows_seen:
            raise ValueError('G17 duplicates a selected series year.')
        rows_seen.add(key)
        if not tail.startswith('   ') or len(tail[3:]) % 10 or len(tail[3:]) > 120:
            raise ValueError(f'G17 monthly cell alignment changed at line {line_number}.')
        year = int(year_text)
        if not 1900 <= year <= as_of.year:
            raise ValueError('G17 observation year outside supported historical range.')
        cells = tail[3:]
        for index in range(12):
            token = cells[index * 10:(index + 1) * 10].strip()
            period = date(year, index + 1, 1)
            if token in {'', 'NA', 'N.A.', 'ND', 'n.a.', '.'}:
                value = None
            else:
                if not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,4})?', token):
                    raise ValueError('G17 numeric notation changed; source review required.')
                try:
                    value = Decimal(token)
                except InvalidOperation:
                    raise ValueError(f'Invalid G17 numeric cell at line {line_number}.') from None
                if not value.is_finite() or value < 0:
                    raise ValueError('G17 production values must be finite and non-negative.')
                if period > as_of:
                    raise ValueError('G17 contains a future observation.')
            if earliest <= period <= as_of:
                observations[code][period.isoformat()[:7]] = {
                    'period': period.isoformat()[:7], 'value': str(value) if value is not None else None,
                    'status': 'OBSERVED' if value is not None else 'UNAVAILABLE', 'source_line': line_number,
                }
    if set(headers) != set(BY_CODE) or any(not values for values in observations.values()):
        raise ValueError('G17 source lacks required selected series or observation history.')
    for code, series in BY_CODE.items():
        if headers[code] != f'{series.title}  NAICS={series.naics}':
            raise ValueError('G17 selected classification changed; registry review required.')
    return {
        'adapter_version': ADAPTER_VERSION, 'source_sha256': sha256(body).hexdigest(),
        'series': [{
            'metadata': series.metadata(), 'source_title': headers[code],
            'observations': [values[period] for period in sorted(values)],
        } for code, series in BY_CODE.items() for values in [observations[code]]],
    }


def transform(observations: list[dict], *, kind: str, periods: int = 36, moving_average: bool = False) -> list[dict]:
    if kind not in {'LEVEL', 'MOM_PERCENT', 'YOY_PERCENT'} or not 1 <= periods <= 60:
        raise ValueError('Unsupported market transformation/window.')
    rows = {row['period']: row for row in observations}
    if len(rows) != len(observations):
        raise ValueError('Duplicate market observation period.')
    published = [period for period, row in rows.items() if row['value'] is not None]
    if not published:
        return []
    latest = date.fromisoformat(max(published) + '-01')

    def level(period: date):
        raw = rows.get(period.isoformat()[:7], {}).get('value')
        return Decimal(raw) if raw is not None else None

    def value(period: date):
        current = level(period)
        if current is None or kind == 'LEVEL':
            return current
        previous = level(month_offset(period, -12 if kind == 'YOY_PERCENT' else -1))
        return None if previous is None or previous == 0 else (current / previous - 1) * 100

    result = []
    for delta in range(-periods + 1, 1):
        period = month_offset(latest, delta)
        values = [value(month_offset(period, -offset)) for offset in range(3 if moving_average else 1)]
        computed = None if any(item is None for item in values) else sum(values) / len(values)
        result.append({'period': period.isoformat()[:7],
                       'value': str(computed.quantize(Decimal('0.0001'))) if computed is not None else None,
                       'status': 'AVAILABLE' if computed is not None else 'UNAVAILABLE'})
    return result
