from datetime import date
from decimal import Decimal

import pytest

from btx_omni.domain.markets import PRIMARY_MARKETS
from btx_omni.modules.markets.g17 import month_offset, parse_g17, transform
from btx_omni.modules.markets.registry import SERIES, coverage


def source(*, values=None, year=2026):
    cells = values if values is not None else ['100', '101', None, '103', '104', '105', '106']
    lines = []
    for series in SERIES:
        lines.append(f'"{series.native_code}: {series.title}  NAICS={series.naics}"')
        lines.append(f'"{series.native_code}"        {year}   ' + ''.join(f'{value or "":>10}' for value in cells))
    return ('\r\n'.join(lines) + '\r\n').encode()


def test_fixed_cells_keep_interior_and_trailing_missing_not_shifted():
    result = parse_g17(source(), as_of=date(2026, 9, 8))
    assert len(result['series']) == 4
    rows = result['series'][0]['observations']
    assert rows[2]['period'] == '2026-03' and rows[2]['value'] is None
    assert rows[3]['value'] == '103'
    assert rows[7]['value'] is None and rows[8]['value'] is None
    assert transform(rows, kind='LEVEL', periods=1)[0]['period'] == '2026-07'


@pytest.mark.parametrize('body', [
    source(values=['NaN']), source(values=['Infinity']), source(values=['-1']),
    source(values=['1e9999']), source(values=['1.123456']),
    source(year=2027), source(values=['100'] * 10), source().replace(b'      2026', b'      XXXX'),
    source().replace(b'NAICS=3364', b'NAICS=9999'), source().replace(b'   2026', b'   2026 '),
    source() + source(), b'<html>Service unavailable</html>',
])
def test_invalid_changed_future_or_duplicate_source_fails_closed(body):
    with pytest.raises(ValueError):
        parse_g17(body, as_of=date(2026, 9, 8))


def test_month_grid_and_transform_are_not_position_based_or_zero_imputed():
    rows = [{'period': '2025-01', 'value': '100'}, {'period': '2025-02', 'value': '0'},
            {'period': '2026-01', 'value': '125'}, {'period': '2026-02', 'value': '130'},
            {'period': '2026-04', 'value': '150'}]
    result = transform(rows, kind='YOY_PERCENT', periods=4)
    assert result == [
        {'period': '2026-01', 'value': '25.0000', 'status': 'AVAILABLE'},
        {'period': '2026-02', 'value': None, 'status': 'UNAVAILABLE'},
        {'period': '2026-03', 'value': None, 'status': 'UNAVAILABLE'},
        {'period': '2026-04', 'value': None, 'status': 'UNAVAILABLE'},
    ]
    assert transform(rows, kind='MOM_PERCENT', periods=1)[0]['value'] is None
    assert transform(rows, kind='LEVEL', periods=1, moving_average=True)[0]['value'] is None
    assert month_offset(date(2026, 1, 1), -1) == date(2025, 12, 1)
    with pytest.raises(ValueError, match='Duplicate'):
        transform(rows + [rows[0]], kind='LEVEL')


def test_three_month_average_requires_all_three_calendar_months():
    rows = [{'period': f'2026-0{month}', 'value': str(month * 10)} for month in range(1, 5)]
    result = transform(rows, kind='LEVEL', periods=4, moving_average=True)
    assert [row['value'] for row in result] == [None, None, '20.0000', '30.0000']
    assert Decimal(transform(rows, kind='MOM_PERCENT', periods=1)[0]['value']) == Decimal('33.3333')


def test_registry_covers_all_markets_honestly_without_duplicating_series():
    matrix = coverage()
    assert {row['market'] for row in matrix} == PRIMARY_MARKETS
    assert next(row for row in matrix if row['market'] == 'Robotics')['status'] == 'UNAVAILABLE'
    shared = [row['series_ids'] for row in matrix if row['market'] in {'Space', 'Defense', 'Commercial Aerospace'}]
    assert shared[0] == shared[1] == shared[2] == ['FED_G17_IP_SA_G3364']
    assert all(row['regional_status'] == 'UNAVAILABLE_FOR_THIS_METRIC' for row in matrix)
    assert all(series.taxonomy == 'NAICS2022' and series.index_base == '2017=100' for series in SERIES)
